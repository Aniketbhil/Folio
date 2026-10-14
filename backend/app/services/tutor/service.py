import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.conversation import Conversation, Message
from app.models.source import Chunk
from app.models.topic import ChunkTopic, Topic
from app.schemas.tutor import (
    DevAskResponse,
    DevAskThresholds,
    DevAskTopHit,
    RelatedTopicItem,
    TutorCitation,
    TutorResponse,
)
from app.models.mastery import Mastery
from app.services.citations import build_citation
from app.services.learner.forgetting import effective_mastery
from app.services.learner.mastery import status_for
from app.services.learner.nudges import apply_chat_nudge
from app.services.llm import get_llm_client
from app.services.retrieval import RetrievedChunk, retrieve
from app.services.tutor.mock import MockTutor, is_followup_message
from app.services.tutor.prompts import (
    TUTOR_ANSWER_USER_PROMPT,
    TUTOR_REWRITE_SYSTEM_PROMPT,
    TUTOR_REWRITE_USER_PROMPT,
    TUTOR_SYSTEM_PROMPT,
)
from app.services.tutor.schemas import TutorLLMOutput

logger = logging.getLogger(__name__)

SMALL_TALK_PATTERN = re.compile(
    r"^(hi|hello|hey|greetings|howdy|thanks|thank you|thx|ok|okay|bye|goodbye|good morning|good afternoon|good evening)[.!]?$",
    re.IGNORECASE,
)

STANDARD_REFUSAL = "I couldn't find this in your course material."


def format_location_str(chunk: Chunk) -> str:
    """Format human-readable source location for prompts and citations."""
    st = (chunk.source_type or "").lower()
    if st == "pdf" and chunk.page_number is not None:
        return f"Page {chunk.page_number}"
    elif st == "slide" and chunk.slide_number is not None:
        return f"Slide {chunk.slide_number}"
    elif st in ("video", "video_transcript") and chunk.start_sec is not None:
        sm, ss = divmod(int(chunk.start_sec), 60)
        em, es = divmod(int(chunk.end_sec or chunk.start_sec), 60)
        return f"{sm:02d}:{ss:02d} - {em:02d}:{es:02d}"
    return "Course Text"


def expand_topic_ids(db: Session, course_id: int, topic_ids: List[int]) -> List[int]:
    """Expand topic IDs to include all their leaf descendant topic IDs."""
    if not topic_ids:
        return []

    all_topics = db.scalars(
        select(Topic).where(Topic.course_id == course_id)
    ).all()
    children_map: Dict[int, List[int]] = {}
    for t in all_topics:
        if t.parent_id is not None:
            children_map.setdefault(t.parent_id, []).append(t.id)

    expanded: Set[int] = set()

    def add_leaves(cur_id: int) -> None:
        children = children_map.get(cur_id, [])
        if not children:
            expanded.add(cur_id)
        else:
            for c in children:
                add_leaves(c)

    for tid in topic_ids:
        add_leaves(tid)

    return list(expanded)


def get_topics_for_chunks(db: Session, chunk_ids: List[int], max_topics: int = 3) -> List[RelatedTopicItem]:
    """Fetch distinct leaf topics mapped to chunk IDs, ordered by chunk association count."""
    if not chunk_ids:
        return []

    rows = db.execute(
        select(Topic.id, Topic.name, func.count(ChunkTopic.chunk_id).label("c_count"))
        .join(ChunkTopic, ChunkTopic.topic_id == Topic.id)
        .where(ChunkTopic.chunk_id.in_(chunk_ids))
        .group_by(Topic.id, Topic.name)
        .order_by(func.count(ChunkTopic.chunk_id).desc(), Topic.name.asc())
        .limit(max_topics)
    ).all()

    return [RelatedTopicItem(id=row[0], name=row[1]) for row in rows]


def build_student_level_hint(
    db: Session,
    student_id: Optional[int],
    retrieved_chunks: List[RetrievedChunk],
) -> Optional[str]:
    """Compute pedagogical hint based on student's mastery in retrieved leaf topics."""
    if not student_id or not retrieved_chunks:
        return None

    top_3_chunk_ids = [rc.chunk.id for rc in retrieved_chunks[:3]]
    topic_rows = db.scalars(
        select(Topic)
        .join(ChunkTopic, ChunkTopic.topic_id == Topic.id)
        .where(ChunkTopic.chunk_id.in_(top_3_chunk_ids))
        .distinct()
    ).all()

    # Filter to leaf topics only
    leaf_topics: List[Topic] = []
    for t in topic_rows:
        has_sub = db.scalar(
            select(func.count(Topic.id)).where(Topic.parent_id == t.id)
        ) or 0
        if has_sub == 0:
            leaf_topics.append(t)

    if not leaf_topics:
        return None

    leaf_ids = [t.id for t in leaf_topics]
    mastery_rows = db.scalars(
        select(Mastery).where(
            Mastery.student_id == student_id,
            Mastery.topic_id.in_(leaf_ids),
        )
    ).all()
    mastery_map = {m.topic_id: m for m in mastery_rows}

    level_lines: List[str] = []
    for t in leaf_topics:
        m = mastery_map.get(t.id)
        if m:
            eff = effective_mastery(m.p_mastery, m.last_practiced_at, m.correct_count)
            st = status_for(eff, m.attempts_count)
        else:
            eff = 0.0
            st = status_for(eff, 0)
        level_lines.append(f"- {t.name}: {st}")

    topic_levels_text = "\n".join(level_lines)
    hint_text = (
        f"STUDENT MASTERY LEVEL:\n"
        f"{topic_levels_text}\n\n"
        f"Pedagogical guidance by level:\n"
        f"- new or weak: explain from the basics, define terms, give one concrete example, mention the prerequisite concept if relevant;\n"
        f"- learning: moderate depth with one example;\n"
        f"- strong: be concise, skip basics, add a deeper insight or common pitfall.\n"
        f"Never claim the student did or did not do something; the level is only a hint for depth."
    )
    return hint_text


class TutorService:
    """Orchestrates conversation history, query rewriting, grounded retrieval, gating, and answer generation."""

    def __init__(self) -> None:
        self.mock_tutor = MockTutor()
        self.rewrite_count: int = 0

    def answer(
        self,
        db: Session,
        conversation: Conversation,
        student_id: int,
        content: str,
        topic_ids: Optional[List[int]] = None,
        debug: bool = False,
    ) -> TutorResponse:
        """Process student message, execute grounded tutor pipeline, persist, and return response."""
        settings = get_settings()
        course_id = conversation.course_id

        # 1. Load conversation history (up to TUTOR_HISTORY_TURNS message pairs)
        max_messages = settings.tutor_history_turns * 2
        history_rows = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(max_messages)
            ).all()
        )
        history_rows.reverse()
        history_list = [{"role": m.role, "content": m.content} for m in history_rows]

        # 2. Small talk shortcut
        trimmed_content = content.strip()
        if SMALL_TALK_PATTERN.match(trimmed_content):
            canned_answer = (
                "Hello! I am your AI study companion. Feel free to ask me any question "
                "about your course materials, concepts, or assignments!"
            )
            user_msg = Message(
                conversation_id=conversation.id,
                role="user",
                content=content,
                grounding_status=None,
                citations=[],
                meta={"topic_ids": topic_ids} if topic_ids else {},
            )
            db.add(user_msg)
            db.flush()

            asst_msg = Message(
                conversation_id=conversation.id,
                role="assistant",
                content=canned_answer,
                grounding_status=None,
                citations=[],
                meta={
                    "outside_knowledge_note": None,
                    "followups": [],
                    "related_topics": [],
                    "top_score": None,
                    "retrieved_chunk_ids": [],
                },
            )
            db.add(asst_msg)
            db.commit()
            db.refresh(user_msg)
            db.refresh(asst_msg)

            return TutorResponse(
                conversation_id=conversation.id,
                user_message_id=user_msg.id,
                message_id=asst_msg.id,
                assistant_message_id=asst_msg.id,
                answer=canned_answer,
                grounding=None,
                citations=[],
                outside_knowledge_note=None,
                followups=[],
                related_topics=[],
            )

        # 3. Query rewrite
        rewritten_query: Optional[str] = None
        search_query = content

        if history_list and is_followup_message(content):
            self.rewrite_count += 1
            if settings.llm_mock:
                rewritten_query = self.mock_tutor.rewrite_query(history_list, content)
                search_query = rewritten_query
            else:
                try:
                    history_text = "\n".join(
                        f"{m['role'].upper()}: {m['content']}" for m in history_list[-4:]
                    )
                    prompt = TUTOR_REWRITE_USER_PROMPT.format(
                        history_text=history_text, question=content
                    )
                    llm = get_llm_client()
                    gen_out = llm.generate_text(prompt, system=TUTOR_REWRITE_SYSTEM_PROMPT).strip()
                    if gen_out:
                        rewritten_query = gen_out
                        search_query = gen_out
                except Exception as exc:
                    logger.warning("Query rewrite failed, falling back to original query: %s", exc)
                    search_query = content

        # 4. Check for embedded chunks in course
        embedded_count = (
            db.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.course_id == course_id, Chunk.embedded == True
                )
            )
            or 0
        )
        if embedded_count == 0:
            raise AppError(
                "Upload and process some material first.",
                code="no_content",
                status_code=409,
            )

        # Expand topic scoping if requested
        scoped_topic_ids: Optional[List[int]] = None
        if topic_ids:
            scoped_topic_ids = expand_topic_ids(db, course_id, topic_ids)

        # 5. Retrieve
        retrieved_chunks = retrieve(
            db=db,
            course_id=course_id,
            query=search_query,
            top_k=settings.tutor_top_k,
            topic_ids=scoped_topic_ids,
        )

        best_score = retrieved_chunks[0].score if retrieved_chunks else 0.0

        # Suggestions for related topics based on top 3 hits
        top_3_chunk_ids = [rc.chunk.id for rc in retrieved_chunks[:3]]
        suggestion_topics = get_topics_for_chunks(db, top_3_chunk_ids, max_topics=3)
        suggestion_names = [t.name for t in suggestion_topics]

        # 6. Gating and LLM generation
        if settings.llm_mock:
            # Mock mode lexical overlap gate and generator
            mock_status, mock_overlap, mock_used = self.mock_tutor.evaluate_grounding(
                search_query, retrieved_chunks
            )
            llm_output = self.mock_tutor.generate_answer(
                query=search_query,
                retrieved=retrieved_chunks,
                grounding=mock_status,
                used_indices=mock_used,
                related_topic_names=suggestion_names,
            )
            gate_decision = "refused_low_score" if mock_status == "unsupported" else "passed"
        else:
            # Live mode similarity score gate
            if not retrieved_chunks or best_score < settings.tutor_min_score:
                gate_decision = "refused_low_score"
                followups = [f"Explain {t}" for t in suggestion_names]
                llm_output = TutorLLMOutput(
                    grounding="unsupported",
                    answer=STANDARD_REFUSAL,
                    used_sources=[],
                    outside_knowledge_note=None,
                    followups=followups,
                )
            else:
                gate_decision = "passed"
                # Prepare numbered sources text
                sources_blocks: List[str] = []
                for idx, rc in enumerate(retrieved_chunks, start=1):
                    loc_str = format_location_str(rc.chunk)
                    text_snip = rc.chunk.text[: settings.tutor_context_chars]
                    sources_blocks.append(
                        f"[{idx}] {rc.source.title} ({loc_str}):\n{text_snip}"
                    )
                sources_text = "\n\n".join(sources_blocks)

                history_text = "\n".join(
                    f"{m['role'].upper()}: {m['content']}" for m in history_list
                )
                student_level_hint = (
                    build_student_level_hint(db, conversation.student_id, retrieved_chunks)
                    if settings.tutor_personalize
                    else None
                )
                student_level_block = f"\n{student_level_hint}\n" if student_level_hint else ""
                answer_prompt = TUTOR_ANSWER_USER_PROMPT.format(
                    sources_text=sources_text,
                    history_text=history_text or "No prior messages.",
                    student_level_block=student_level_block,
                    question=content,
                )

                try:
                    llm = get_llm_client()
                    llm_output = llm.generate_json(
                        prompt=answer_prompt,
                        schema=TutorLLMOutput,
                        system=TUTOR_SYSTEM_PROMPT,
                    )
                except Exception as exc:
                    logger.error("LLM tutor answer generation failed: %s", exc)
                    raise AppError(
                        "Failed to generate tutor answer. Please try again.",
                        code="llm_invalid_output",
                        status_code=502,
                    )

        # 7. Server-side validation and marker renumbering
        raw_answer = llm_output.answer
        total_retrieved = len(retrieved_chunks)

        # Parse [n] markers in answer and merge with used_sources
        seen_indices: Set[int] = set()
        final_source_indices: List[int] = []

        for match in re.finditer(r"\[(\d+)\]", raw_answer):
            src_num = int(match.group(1))
            if 1 <= src_num <= total_retrieved and src_num not in seen_indices:
                seen_indices.add(src_num)
                final_source_indices.append(src_num)

        for src_num in llm_output.used_sources:
            if 1 <= src_num <= total_retrieved and src_num not in seen_indices:
                seen_indices.add(src_num)
                final_source_indices.append(src_num)

        # Mapping from original source index to consecutive 1-based ref
        old_to_new = {
            old_idx: new_ref
            for new_ref, old_idx in enumerate(final_source_indices, start=1)
        }

        def _replace_marker(m: re.Match) -> str:
            val = int(m.group(1))
            if val in old_to_new:
                return f"[{old_to_new[val]}]"
            return ""

        renumbered_answer = re.sub(r"\[(\d+)\]", _replace_marker, raw_answer)
        renumbered_answer = re.sub(r"[ \t]+", " ", renumbered_answer).strip()

        # Build final citations
        final_citations: List[TutorCitation] = []
        for new_ref, old_idx in enumerate(final_source_indices, start=1):
            rc = retrieved_chunks[old_idx - 1]
            cit = build_citation(rc.chunk, rc.source, score=rc.score)
            final_citations.append(
                TutorCitation(**cit.model_dump(), ref=new_ref)
            )

        # Apply grounding downgrade rules
        grounding_result = llm_output.grounding
        outside_note = llm_output.outside_knowledge_note

        if grounding_result in ("grounded", "partial") and len(final_citations) == 0:
            grounding_result = "unsupported"
            renumbered_answer = STANDARD_REFUSAL
            outside_note = None

        if grounding_result == "grounded" and "Outside your material:" in renumbered_answer:
            grounding_result = "partial"

        if grounding_result == "unsupported":
            final_citations = []
            outside_note = None

        # 8. Compute related_topics
        if final_citations:
            cited_chunk_ids = [c.chunk_id for c in final_citations]
            related_topics = get_topics_for_chunks(db, cited_chunk_ids, max_topics=3)
        else:
            related_topics = suggestion_topics if grounding_result == "unsupported" else []

        followups = llm_output.followups
        if not followups and related_topics:
            followups = [f"Explain {t.name}" for t in related_topics]

        # Apply chat mastery nudge
        mastery_nudge: Optional[Dict[str, Any]] = None
        if grounding_result in ("grounded", "partial") and related_topics:
            try:
                nudges = apply_chat_nudge(db, conversation.student_id, [t.id for t in related_topics])
                if nudges:
                    mastery_nudge = nudges[0]
            except Exception as exc:
                logger.warning("Chat mastery nudge failed: %s", exc)

        # 9. Persist messages and update conversation title
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=content,
            grounding_status=None,
            citations=[],
            meta={"topic_ids": topic_ids} if topic_ids else {},
        )
        db.add(user_msg)
        db.flush()

        asst_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=renumbered_answer,
            grounding_status=grounding_result,
            citations=[c.model_dump() for c in final_citations],
            meta={
                "outside_knowledge_note": outside_note,
                "followups": followups,
                "related_topics": [t.model_dump() for t in related_topics],
                "top_score": round(best_score, 4) if best_score is not None else None,
                "retrieved_chunk_ids": [rc.chunk.id for rc in retrieved_chunks],
                "mastery_nudge": mastery_nudge,
            },
        )
        db.add(asst_msg)

        # Auto-set conversation title from first question if default
        if not conversation.title or conversation.title == "New Conversation":
            clean_q = re.sub(r"\s+", " ", content).strip()
            if len(clean_q) <= 60:
                conversation.title = clean_q
            else:
                truncated = clean_q[:60]
                last_space = truncated.rfind(" ")
                if last_space > 0:
                    truncated = truncated[:last_space]
                conversation.title = truncated.rstrip(".,;:- ")

        db.commit()
        db.refresh(user_msg)
        db.refresh(asst_msg)

        return TutorResponse(
            conversation_id=conversation.id,
            user_message_id=user_msg.id,
            message_id=asst_msg.id,
            assistant_message_id=asst_msg.id,
            answer=renumbered_answer,
            grounding=grounding_result,
            citations=final_citations,
            outside_knowledge_note=outside_note,
            followups=followups,
            related_topics=related_topics,
            mastery_nudge=mastery_nudge,
        )

    def ask_dev(
        self,
        db: Session,
        course_id: int,
        question: str,
        student_id: Optional[int] = None,
        topic_ids: Optional[List[int]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> DevAskResponse:
        """Dev inspection: runs retrieval + gate + answer WITHOUT persisting anything."""
        settings = get_settings()

        rewritten_query: Optional[str] = None
        search_query = question

        if history and is_followup_message(question):
            self.rewrite_count += 1
            if settings.llm_mock:
                rewritten_query = self.mock_tutor.rewrite_query(history, question)
                search_query = rewritten_query
            else:
                try:
                    history_text = "\n".join(
                        f"{m['role'].upper()}: {m['content']}" for m in history[-4:]
                    )
                    prompt = TUTOR_REWRITE_USER_PROMPT.format(
                        history_text=history_text, question=question
                    )
                    llm = get_llm_client()
                    gen_out = llm.generate_text(prompt, system=TUTOR_REWRITE_SYSTEM_PROMPT).strip()
                    if gen_out:
                        rewritten_query = gen_out
                        search_query = gen_out
                except Exception as exc:
                    logger.warning("Query rewrite failed in dev ask: %s", exc)

        embedded_count = (
            db.scalar(
                select(func.count(Chunk.id)).where(
                    Chunk.course_id == course_id, Chunk.embedded == True
                )
            )
            or 0
        )
        if embedded_count == 0:
            raise AppError(
                "Upload and process some material first.",
                code="no_content",
                status_code=409,
            )

        scoped_topic_ids: Optional[List[int]] = None
        if topic_ids:
            scoped_topic_ids = expand_topic_ids(db, course_id, topic_ids)

        retrieved_chunks = retrieve(
            db=db,
            course_id=course_id,
            query=search_query,
            top_k=settings.tutor_top_k,
            topic_ids=scoped_topic_ids,
        )

        student_level_hint = (
            build_student_level_hint(db, student_id, retrieved_chunks)
            if settings.tutor_personalize and student_id
            else None
        )

        best_score = retrieved_chunks[0].score if retrieved_chunks else 0.0

        top_hits = [
            DevAskTopHit(
                chunk_id=rc.chunk.id,
                score=round(rc.score, 4),
                location=build_citation(rc.chunk, rc.source).location,
                snippet=build_citation(rc.chunk, rc.source).snippet,
            )
            for rc in retrieved_chunks
        ]

        # Suggestions
        top_3_chunk_ids = [rc.chunk.id for rc in retrieved_chunks[:3]]
        suggestion_topics = get_topics_for_chunks(db, top_3_chunk_ids, max_topics=3)
        suggestion_names = [t.name for t in suggestion_topics]

        raw_llm_dict: Optional[Dict[str, Any]] = None

        if settings.llm_mock:
            mock_status, mock_overlap, mock_used = self.mock_tutor.evaluate_grounding(
                question, retrieved_chunks
            )
            llm_output = self.mock_tutor.generate_answer(
                query=question,
                retrieved=retrieved_chunks,
                grounding=mock_status,
                used_indices=mock_used,
                related_topic_names=suggestion_names,
            )
            gate_decision = "refused_low_score" if mock_status == "unsupported" else "passed"
        else:
            if not retrieved_chunks or best_score < settings.tutor_min_score:
                gate_decision = "refused_low_score"
                followups = [f"Explain {t}" for t in suggestion_names]
                llm_output = TutorLLMOutput(
                    grounding="unsupported",
                    answer=STANDARD_REFUSAL,
                    used_sources=[],
                    outside_knowledge_note=None,
                    followups=followups,
                )
            else:
                gate_decision = "passed"
                sources_blocks = [
                    f"[{idx}] {rc.source.title} ({format_location_str(rc.chunk)}):\n{rc.chunk.text[: settings.tutor_context_chars]}"
                    for idx, rc in enumerate(retrieved_chunks, start=1)
                ]
                sources_text = "\n\n".join(sources_blocks)
                student_level_block = f"\n{student_level_hint}\n" if student_level_hint else ""
                answer_prompt = TUTOR_ANSWER_USER_PROMPT.format(
                    sources_text=sources_text,
                    history_text="No prior messages.",
                    student_level_block=student_level_block,
                    question=question,
                )
                llm = get_llm_client()
                llm_output = llm.generate_json(
                    prompt=answer_prompt,
                    schema=TutorLLMOutput,
                    system=TUTOR_SYSTEM_PROMPT,
                )
                raw_llm_dict = llm_output.model_dump()

        # Validation & Renumbering
        raw_answer = llm_output.answer
        seen_indices: Set[int] = set()
        final_source_indices: List[int] = []

        for match in re.finditer(r"\[(\d+)\]", raw_answer):
            src_num = int(match.group(1))
            if 1 <= src_num <= len(retrieved_chunks) and src_num not in seen_indices:
                seen_indices.add(src_num)
                final_source_indices.append(src_num)

        for src_num in llm_output.used_sources:
            if 1 <= src_num <= len(retrieved_chunks) and src_num not in seen_indices:
                seen_indices.add(src_num)
                final_source_indices.append(src_num)

        old_to_new = {
            old_idx: new_ref
            for new_ref, old_idx in enumerate(final_source_indices, start=1)
        }

        def _replace_marker(m: re.Match) -> str:
            val = int(m.group(1))
            if val in old_to_new:
                return f"[{old_to_new[val]}]"
            return ""

        renumbered_answer = re.sub(r"\[(\d+)\]", _replace_marker, raw_answer)
        renumbered_answer = re.sub(r"[ \t]+", " ", renumbered_answer).strip()

        final_citations = [
            TutorCitation(
                **build_citation(
                    retrieved_chunks[old_idx - 1].chunk,
                    retrieved_chunks[old_idx - 1].source,
                    score=retrieved_chunks[old_idx - 1].score,
                ).model_dump(),
                ref=new_ref,
            )
            for new_ref, old_idx in enumerate(final_source_indices, start=1)
        ]

        grounding_result = llm_output.grounding
        outside_note = llm_output.outside_knowledge_note

        if grounding_result in ("grounded", "partial") and len(final_citations) == 0:
            grounding_result = "unsupported"
            renumbered_answer = STANDARD_REFUSAL
            outside_note = None

        if grounding_result == "grounded" and "Outside your material:" in renumbered_answer:
            grounding_result = "partial"

        if grounding_result == "unsupported":
            final_citations = []
            outside_note = None

        if final_citations:
            cited_chunk_ids = [c.chunk_id for c in final_citations]
            related_topics = get_topics_for_chunks(db, cited_chunk_ids, max_topics=3)
        else:
            related_topics = suggestion_topics if grounding_result == "unsupported" else []

        followups = llm_output.followups
        if not followups and related_topics:
            followups = [f"Explain {t.name}" for t in related_topics]

        final_response_dict = {
            "answer": renumbered_answer,
            "grounding": grounding_result,
            "citations": [c.model_dump() for c in final_citations],
            "outside_knowledge_note": outside_note,
            "followups": followups,
            "related_topics": [t.model_dump() for t in related_topics],
        }

        return DevAskResponse(
            rewritten_query=rewritten_query,
            top_hits=top_hits,
            best_score=round(best_score, 4),
            gate=gate_decision,
            gate_decision=gate_decision,
            thresholds=DevAskThresholds(
                min=settings.tutor_min_score,
                strong=settings.tutor_strong_score,
                mock_min_overlap=settings.tutor_mock_min_overlap,
            ),
            mode="mock" if settings.llm_mock else "live",
            raw_llm_output=raw_llm_dict,
            student_level_hint=student_level_hint,
            final_response=final_response_dict,
        )


_tutor_service = TutorService()


def get_tutor_service() -> TutorService:
    """Singleton getter for TutorService."""
    return _tutor_service
