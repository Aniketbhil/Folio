from datetime import datetime, timezone
import logging
import math
import re
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.models.assessment import Attempt, Question
from app.models.course import Course
from app.models.mastery import Mastery, MasteryEvent
from app.models.source import Chunk, Source
from app.models.topic import (
    ChunkConcept,
    ChunkTopic,
    Concept,
    Topic,
    TopicPrereq,
)
from app.services.ingestion.chunking import estimate_tokens
from app.services.kb.heuristic import HeuristicKBBuilder
from app.services.kb.prompts import (
    KB_MAP_SYSTEM_PROMPT,
    KB_MAP_USER_PROMPT,
    KB_REDUCE_SYSTEM_PROMPT,
    KB_REDUCE_USER_PROMPT,
    KB_TAG_SYSTEM_PROMPT,
    KB_TAG_USER_PROMPT,
)
from app.services.kb.schemas import (
    CandidateTopic,
    ChunkTagItem,
    MapTopicsOutput,
    SubtopicOutput,
    TagBatchOutput,
    TaxonomyOutput,
    TopTopicOutput,
)
from app.services.llm import get_llm_client

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Normalize topic or concept name for consistent matching."""
    return re.sub(r"\s+", " ", name.strip().lower())


def _has_path(adj: Dict[str, Set[str]], start: str, target: str) -> bool:
    """Check if a directed path exists from start to target (for cycle detection)."""
    visited: Set[str] = set()
    queue = [start]
    while queue:
        curr = queue.pop()
        if curr == target:
            return True
        if curr not in visited:
            visited.add(curr)
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    queue.append(neighbor)
    return False


def build_knowledge_base(
    course_id: int,
    progress_callback: Optional[Callable[[str, int], None]] = None,
) -> None:
    """Orchestrate knowledge base building for a course.

    Uses its own database session and handles MAP, REDUCE, TAG, and transactional SAVE.
    """
    settings = get_settings()

    def update_progress(stage: str, prog: int) -> None:
        if progress_callback:
            progress_callback(stage, prog)

    with SessionLocal() as db:
        course = db.get(Course, course_id)
        if not course:
            logger.error("Course %d not found for KB build.", course_id)
            return

        # 1. Fetch chunks ordered by source_id, chunk_index
        chunks = list(
            db.scalars(
                select(Chunk)
                .where(Chunk.course_id == course_id)
                .order_by(Chunk.source_id.asc(), Chunk.chunk_index.asc())
            ).all()
        )

        sources = {
            s.id: s
            for s in db.scalars(
                select(Source).where(Source.course_id == course_id)
            ).all()
        }

        # If no chunks remain, reset KB state to empty
        if not chunks:
            course.kb_status = "empty"
            course.kb_error = None
            course.kb_built_at = None

            # Clear any existing topics
            topic_ids = list(
                db.scalars(select(Topic.id).where(Topic.course_id == course_id)).all()
            )
            if topic_ids:
                db.execute(delete(TopicPrereq).where(TopicPrereq.course_id == course_id))
                db.execute(delete(ChunkTopic).where(ChunkTopic.topic_id.in_(topic_ids)))
                db.execute(
                    delete(ChunkConcept).where(
                        ChunkConcept.concept_id.in_(
                            select(Concept.id).where(Concept.course_id == course_id)
                        )
                    )
                )
                db.execute(delete(Concept).where(Concept.course_id == course_id))
                db.execute(delete(Topic).where(Topic.course_id == course_id))
            db.commit()
            update_progress("done", 100)
            logger.info("Course %d has no chunks; cleared KB and set status to empty.", course_id)
            return

        # Mark course as building
        course.kb_status = "building"
        course.kb_error = None
        db.commit()

        try:
            update_progress("mapping", 10)

            # 2. Heuristic or Live LLM workflow
            if settings.llm_mock:
                logger.info("Executing HeuristicKBBuilder for course %d (LLM_MOCK=true).", course_id)
                taxonomy, tag_items = HeuristicKBBuilder().build(chunks, sources)
                update_progress("saving", 90)
            else:
                llm = get_llm_client()
                logger.info("Executing LLM KB builder for course %d.", course_id)

                # MAP STEP: batch chunks by KB_BATCH_TOKENS
                candidate_topics: List[CandidateTopic] = []
                batch_chunks: List[str] = []
                curr_tokens = 0

                for c in chunks:
                    chunk_repr = f"Chunk {c.id}"
                    if c.section_title:
                        chunk_repr += f" [{c.section_title}]"
                    chunk_repr += f": {c.text[:400]}"
                    t_count = estimate_tokens(chunk_repr)

                    if curr_tokens + t_count > settings.kb_batch_tokens and batch_chunks:
                        user_p = KB_MAP_USER_PROMPT.format(chunk_excerpts="\n\n".join(batch_chunks))
                        map_resp = llm.generate_json(user_p, MapTopicsOutput, system=KB_MAP_SYSTEM_PROMPT)
                        candidate_topics.extend(map_resp.topics)
                        batch_chunks = []
                        curr_tokens = 0

                    batch_chunks.append(chunk_repr)
                    curr_tokens += t_count

                if batch_chunks:
                    user_p = KB_MAP_USER_PROMPT.format(chunk_excerpts="\n\n".join(batch_chunks))
                    map_resp = llm.generate_json(user_p, MapTopicsOutput, system=KB_MAP_SYSTEM_PROMPT)
                    candidate_topics.extend(map_resp.topics)

                update_progress("taxonomy", 40)

                # REDUCE STEP: synthesize hierarchy
                source_titles_str = ", ".join(s.title for s in sources.values())
                candidates_text = "\n".join(
                    f"- {t.name}: {t.description}" for t in candidate_topics[:50]
                )
                reduce_user_p = KB_REDUCE_USER_PROMPT.format(
                    course_name=course.name,
                    source_titles=source_titles_str,
                    candidate_topics_text=candidates_text,
                )
                reduce_sys_p = KB_REDUCE_SYSTEM_PROMPT.format(
                    max_toplevel=settings.kb_max_toplevel,
                    max_subtopics=settings.kb_max_subtopics,
                )
                taxonomy = llm.generate_json(reduce_user_p, TaxonomyOutput, system=reduce_sys_p)

                update_progress("tagging", 65)

                # Collect leaf topics for tagging
                leaf_names = []
                for top in taxonomy.topics:
                    for sub in top.subtopics:
                        leaf_names.append(sub.name)
                leaf_list_str = "\n".join(f"- {name}" for name in leaf_names)

                # TAG STEP: batches of ~15-20 chunks
                tag_items: List[ChunkTagItem] = []
                chunk_batch_size = 18

                for i in range(0, len(chunks), chunk_batch_size):
                    c_slice = chunks[i : i + chunk_batch_size]
                    chunks_payload = "\n\n".join(
                        f"Chunk ID: {c.id}\nContent: {c.text[:1200]}" for c in c_slice
                    )
                    tag_user_p = KB_TAG_USER_PROMPT.format(
                        leaf_topics_list=leaf_list_str,
                        chunks_to_tag=chunks_payload,
                    )
                    tag_resp = llm.generate_json(tag_user_p, TagBatchOutput, system=KB_TAG_SYSTEM_PROMPT)
                    tag_items.extend(tag_resp.chunks)

                update_progress("saving", 85)

            # 3. VALIDATE, PRUNE, AND PERSIST
            _persist_knowledge_base(db, course_id, taxonomy, tag_items, chunks)

            # Finalize course state
            course.kb_status = "ready"
            course.kb_error = None
            course.kb_built_at = datetime.now(timezone.utc)
            db.commit()

            update_progress("done", 100)
            logger.info("Successfully built and saved knowledge base for course %d.", course_id)

        except Exception as exc:
            db.rollback()
            logger.exception("KB build failed for course %d: %s", course_id, exc)
            course = db.get(Course, course_id)
            if course:
                course.kb_status = "failed"
                course.kb_error = (
                    exc.message if isinstance(exc, AppError) else str(exc) or "Knowledge base generation failed."
                )
                db.commit()
            update_progress("failed", 0)


def _persist_knowledge_base(
    db: Session,
    course_id: int,
    taxonomy: TaxonomyOutput,
    tag_items: List[ChunkTagItem],
    chunks: List[Chunk],
) -> None:
    """Validate, prune unreferenced topics, resolve DAG prerequisites, and upsert records."""
    # 1. Map chunk tags
    tags_by_chunk_id: Dict[int, ChunkTagItem] = {item.chunk_id: item for item in tag_items}

    # Count chunk assignments per normalized leaf name
    leaf_chunk_counts: Dict[str, int] = {}
    for item in tag_items:
        for t_assign in item.topics:
            norm = _normalize_name(t_assign.name)
            leaf_chunk_counts[norm] = leaf_chunk_counts.get(norm, 0) + 1

    # 2. Prune taxonomy: drop leaves with zero chunks, drop parents with no children
    pruned_top_topics: List[TopTopicOutput] = []

    for top in taxonomy.topics:
        retained_subtopics: List[SubtopicOutput] = []
        for sub in top.subtopics:
            norm_sub = _normalize_name(sub.name)
            # If subtopic was assigned to at least 1 chunk
            if leaf_chunk_counts.get(norm_sub, 0) > 0:
                retained_subtopics.append(sub)

        # If all leaves had 0 chunks but this is the only structure, keep subtopics
        if not retained_subtopics and top.subtopics and not any(leaf_chunk_counts.values()):
            retained_subtopics = top.subtopics

        if retained_subtopics:
            top.subtopics = retained_subtopics
            pruned_top_topics.append(top)

    if not pruned_top_topics and taxonomy.topics:
        pruned_top_topics = taxonomy.topics

    # 3. UPSERT Topics to preserve IDs across rebuilds
    existing_topics = list(
        db.scalars(select(Topic).where(Topic.course_id == course_id)).all()
    )
    existing_roots = {
        _normalize_name(t.name): t for t in existing_topics if t.parent_id is None
    }
    existing_children = {
        (t.parent_id, _normalize_name(t.name)): t
        for t in existing_topics
        if t.parent_id is not None
    }

    retained_topic_ids: Set[int] = set()
    leaf_topic_map: Dict[str, Topic] = {}  # norm_name -> Topic model

    for top_idx, top in enumerate(pruned_top_topics):
        norm_top = _normalize_name(top.name)
        if norm_top in existing_roots:
            db_top = existing_roots[norm_top]
            db_top.name = top.name
            db_top.description = top.description
            db_top.order_index = top_idx + 1
        else:
            db_top = Topic(
                course_id=course_id,
                parent_id=None,
                name=top.name,
                description=top.description,
                order_index=top_idx + 1,
            )
            db.add(db_top)
            db.flush()

        retained_topic_ids.add(db_top.id)

        for sub_idx, sub in enumerate(top.subtopics):
            norm_sub = _normalize_name(sub.name)
            child_key = (db_top.id, norm_sub)

            if child_key in existing_children:
                db_sub = existing_children[child_key]
                db_sub.name = sub.name
                db_sub.description = sub.description
                db_sub.order_index = sub.teaching_order or (sub_idx + 1)
            else:
                db_sub = Topic(
                    course_id=course_id,
                    parent_id=db_top.id,
                    name=sub.name,
                    description=sub.description,
                    order_index=sub.teaching_order or (sub_idx + 1),
                )
                db.add(db_sub)
                db.flush()

            retained_topic_ids.add(db_sub.id)
            leaf_topic_map[norm_sub] = db_sub

    # 4. Clear derived association tables for this course
    all_prev_topic_ids = [t.id for t in existing_topics] + list(retained_topic_ids)
    if all_prev_topic_ids:
        db.execute(delete(TopicPrereq).where(TopicPrereq.course_id == course_id))
        db.execute(delete(ChunkTopic).where(ChunkTopic.topic_id.in_(all_prev_topic_ids)))
        c_ids = list(
            db.scalars(select(Concept.id).where(Concept.course_id == course_id)).all()
        )
        if c_ids:
            db.execute(delete(ChunkConcept).where(ChunkConcept.concept_id.in_(c_ids)))
        db.execute(delete(Concept).where(Concept.course_id == course_id))
    db.flush()

    # 5. Clean up topics removed in this rebuild
    topics_to_delete = [t for t in existing_topics if t.id not in retained_topic_ids]
    if topics_to_delete:
        del_ids = [t.id for t in topics_to_delete]
        db.execute(update(Topic).where(Topic.id.in_(del_ids)).values(parent_id=None))
        for dt in topics_to_delete:
            db.execute(delete(MasteryEvent).where(MasteryEvent.topic_id == dt.id))
            db.execute(delete(Mastery).where(Mastery.topic_id == dt.id))
            q_ids = list(
                db.scalars(select(Question.id).where(Question.topic_id == dt.id)).all()
            )
            if q_ids:
                db.execute(delete(Attempt).where(Attempt.question_id.in_(q_ids)))
                db.execute(delete(Question).where(Question.topic_id == dt.id))
            db.delete(dt)
        db.flush()

    # 6. Build and validate prerequisite edges (DAG verification using DFS)
    prereq_graph: Dict[str, Set[str]] = {}
    valid_edges: Set[Tuple[int, int]] = set()  # (topic_id, prereq_topic_id)

    for top in pruned_top_topics:
        for sub in top.subtopics:
            target_norm = _normalize_name(sub.name)
            target_model = leaf_topic_map.get(target_norm)
            if not target_model:
                continue

            for prereq_name in sub.prerequisites:
                prereq_norm = _normalize_name(prereq_name)
                # No self-edges
                if prereq_norm == target_norm:
                    continue
                prereq_model = leaf_topic_map.get(prereq_norm)
                if not prereq_model:
                    continue

                # Check if adding prereq_norm -> target_norm would create a cycle
                if _has_path(prereq_graph, target_norm, prereq_norm):
                    logger.warning(
                        "Cycle detected for prerequisite '%s' -> '%s'. Dropping edge.",
                        prereq_name,
                        sub.name,
                    )
                    continue

                prereq_graph.setdefault(prereq_norm, set()).add(target_norm)
                valid_edges.add((target_model.id, prereq_model.id))

    for topic_id, prereq_id in valid_edges:
        db.add(
            TopicPrereq(
                topic_id=topic_id,
                prereq_topic_id=prereq_id,
                course_id=course_id,
            )
        )

    # 7. Persist ChunkTopic tags
    chunk_topic_pairs: Set[Tuple[int, int]] = set()
    for item in tag_items:
        chunk_id = item.chunk_id
        for t_assign in item.topics:
            norm_leaf = _normalize_name(t_assign.name)
            topic_model = leaf_topic_map.get(norm_leaf)
            if not topic_model:
                continue

            pair = (chunk_id, topic_model.id)
            if pair not in chunk_topic_pairs:
                chunk_topic_pairs.add(pair)
                rel = max(0.0, min(1.0, float(t_assign.relevance)))
                db.add(
                    ChunkTopic(
                        chunk_id=chunk_id,
                        topic_id=topic_model.id,
                        relevance=rel,
                    )
                )

    # 8. Persist Concepts and ChunkConcept links
    concept_map: Dict[Tuple[int, str], Concept] = {}
    chunk_concept_pairs: Set[Tuple[int, int]] = set()

    for item in tag_items:
        chunk_id = item.chunk_id
        for c_tag in item.concepts:
            norm_leaf = _normalize_name(c_tag.topic_name)
            topic_model = leaf_topic_map.get(norm_leaf)
            if not topic_model:
                continue

            concept_name = c_tag.name.strip()
            norm_cname = _normalize_name(concept_name)
            concept_key = (topic_model.id, norm_cname)

            if concept_key not in concept_map:
                concept_obj = Concept(
                    course_id=course_id,
                    topic_id=topic_model.id,
                    name=concept_name,
                    definition=c_tag.definition.strip() or f"Definition of {concept_name}",
                )
                db.add(concept_obj)
                db.flush()
                concept_map[concept_key] = concept_obj
            else:
                concept_obj = concept_map[concept_key]

            pair = (chunk_id, concept_obj.id)
            if pair not in chunk_concept_pairs:
                chunk_concept_pairs.add(pair)
                db.add(
                    ChunkConcept(
                        chunk_id=chunk_id,
                        concept_id=concept_obj.id,
                    )
                )

    db.flush()
