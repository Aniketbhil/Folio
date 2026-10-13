"""Assessment question generation (live LLM and deterministic mock)."""

import logging
import random
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.config import get_settings
from app.models.topic import Concept
from app.services.assessment.dedupe import compute_prompt_fingerprint
from app.services.assessment.prompts import (
    QUESTION_GENERATION_SYSTEM_PROMPT,
    QUESTION_GENERATION_USER_PROMPT,
)
from app.services.assessment.schemas import (
    CandidateQuestion,
    GeneratedQuestionLLM,
    TopicGenerationLLMOutput,
)
from app.services.assessment.selection import TopicContext
from app.services.kb.heuristic import _extract_first_sentence
from app.services.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


def format_sources_for_prompt(context: TopicContext, max_chars: int) -> str:
    """Format numbered source excerpts [1]..[N] for generation prompt."""
    blocks: List[str] = []
    for idx, c in enumerate(context.chunks, start=1):
        src = context.source_map.get(c.source_id)
        title = src.title if src else "Course Material"
        loc_str = ""
        if c.source_type == "pdf" and c.page_number is not None:
            loc_str = f"Page {c.page_number}"
        elif c.source_type == "slide" and c.slide_number is not None:
            loc_str = f"Slide {c.slide_number}"
        elif c.source_type == "video" and c.start_sec is not None:
            sm, ss = divmod(int(c.start_sec), 60)
            loc_str = f"Time {sm:02d}:{ss:02d}"

        loc_label = f" ({loc_str})" if loc_str else ""
        text_truncated = c.text[:max_chars].strip()
        blocks.append(f"[{idx}] {title}{loc_label}:\n{text_truncated}")

    return "\n\n".join(blocks)


def map_concept_name_to_id(concept_name: Optional[str], candidate_concepts: List[Concept]) -> Optional[int]:
    """Resolve LLM concept name to a real Concept id via normalized matching."""
    if not concept_name or not candidate_concepts:
        return None

    clean_target = re.sub(r"[^a-zA-Z0-9]", "", concept_name.lower())
    for conc in candidate_concepts:
        clean_conc = re.sub(r"[^a-zA-Z0-9]", "", conc.name.lower())
        if clean_target == clean_conc or clean_target in clean_conc or clean_conc in clean_target:
            return conc.id
    return None


def process_mcq_options(
    raw_options: Optional[List[str]],
    raw_correct_idx: Optional[int],
    seed: int,
) -> Optional[Tuple[List[Dict[str, str]], str]]:
    """Shuffle options and assign keys A-D.

    Returns:
        (formatted_options, correct_letter) or None if invalid
    """
    if not raw_options or len(raw_options) < 4:
        return None

    cleaned_options = [opt.strip() for opt in raw_options[:4]]
    # Reject duplicate option texts
    if len(set(cleaned_options)) < 4 or any(len(o) == 0 for o in cleaned_options):
        return None

    correct_idx = raw_correct_idx if raw_correct_idx is not None and 0 <= raw_correct_idx < 4 else 0
    correct_text = cleaned_options[correct_idx]

    # Seeded random shuffle
    rng = random.Random(seed)
    shuffled = list(cleaned_options)
    rng.shuffle(shuffled)

    keys = ["A", "B", "C", "D"]
    final_options: List[Dict[str, str]] = []
    correct_letter = "A"

    for key, text in zip(keys, shuffled):
        final_options.append({"key": key, "text": text})
        if text == correct_text:
            correct_letter = key

    return final_options, correct_letter


class MockQuestionGenerator:
    """Deterministic question generator when LLM_MOCK=true."""

    def __init__(self, all_course_concepts: List[str]) -> None:
        self.all_course_concepts = all_course_concepts

    def generate_for_topic(
        self,
        context: TopicContext,
        do_not_repeat_prompts: List[str],
        seed: int,
    ) -> List[CandidateQuestion]:
        """Generate cloze MCQs and short answer questions deterministically from chunk text."""
        candidates: List[CandidateQuestion] = []
        if not context.chunks:
            return []

        # Candidate distractors from course concepts
        distractor_pool = [
            c for c in self.all_course_concepts if c not in [conc.name for conc in context.concepts]
        ]
        if len(distractor_pool) < 3:
            distractor_pool = ["Inertia", "Acceleration", "Velocity", "Momentum", "Conservation", "Force"]

        do_not_repeat_fps = {compute_prompt_fingerprint(p) for p in do_not_repeat_prompts}
        batch_fps: Set[str] = set()

        mcq_templates = [
            "Which concept best completes the following statement from the study materials: '{text}... relating to _____?'",
            "Identify the foundational principle illustrated by: '{text}... involving _____.'",
            "According to classical principles, which concept explains: '{text}... characterized by _____?'",
            "What core concept is demonstrated in: '{text}... concerning _____?'",
            "Which term describes the physical phenomenon: '{text}... connected with _____?'",
            "Select the concept that directly governs the dynamics of: '{text}... involving _____.'",
            "In classical analysis, which principle underlies: '{text}... pertaining to _____?'",
        ]

        sa_templates = [
            "Explain the principle and significance of {concept_name} as detailed in the course material.",
            "Describe the key characteristics and applications of {concept_name}.",
            "Outline the fundamental properties and theoretical role of {concept_name}.",
            "How is {concept_name} defined and applied in modern dynamics?",
            "Summarize the governing rules and implications of {concept_name}.",
            "Clarify the physical meaning and primary consequences of {concept_name}.",
            "Discuss the core mechanism and theoretical foundation of {concept_name}.",
        ]

        for q_idx in range(context.requested_count):
            qtype = context.assigned_qtypes[q_idx] if q_idx < len(context.assigned_qtypes) else "mcq"
            diff = context.assigned_difficulties[q_idx] if q_idx < len(context.assigned_difficulties) else "medium"
            chunk = context.chunks[q_idx % len(context.chunks)]

            # Target concept if available
            concept_obj = (
                context.concepts[q_idx % len(context.concepts)]
                if context.concepts
                else None
            )
            concept_name = concept_obj.name if concept_obj else "Principles"

            sentences = [
                s.strip()
                for s in re.split(r"(?<=[.!?])\s+", chunk.text)
                if len(s.strip()) > 15
            ]
            if not sentences:
                sentences = [_extract_first_sentence(chunk.text)]

            if qtype == "mcq":
                # Find an unused prompt by varying template and sentence
                chosen_prompt = ""
                chosen_sent = sentences[0]
                for t_idx, tmpl in enumerate(mcq_templates):
                    sent_cand = sentences[(q_idx + t_idx) % len(sentences)]
                    cand_prompt = tmpl.format(text=sent_cand[:90].strip())
                    cand_fp = compute_prompt_fingerprint(cand_prompt)
                    if cand_fp not in do_not_repeat_fps and cand_fp not in batch_fps:
                        chosen_prompt = cand_prompt
                        chosen_sent = sent_cand
                        break

                if not chosen_prompt:
                    chosen_sent = sentences[q_idx % len(sentences)]
                    chosen_prompt = mcq_templates[q_idx % len(mcq_templates)].format(text=chosen_sent[:90].strip()) + f" (Variant {q_idx + seed % 100})"

                batch_fps.add(compute_prompt_fingerprint(chosen_prompt))
                correct_text = concept_name
                # Select 3 distinct distractors
                rng = random.Random(seed + q_idx * 13)
                distractors = rng.sample(distractor_pool, min(3, len(distractor_pool)))
                while len(distractors) < 3:
                    distractors.append(f"Option {len(distractors) + 1}")

                raw_opts = [correct_text] + distractors[:3]
                processed = process_mcq_options(raw_opts, 0, seed + q_idx * 17)
                if not processed:
                    continue
                opts, correct_key = processed

                meta = {"verification": {"mode": "mock", "rule": "cloze"}}
                cq = CandidateQuestion(
                    topic_id=context.topic.id,
                    concept_id=concept_obj.id if concept_obj else None,
                    qtype="mcq",
                    difficulty=diff,
                    prompt=chosen_prompt,
                    options=opts,
                    correct_answer=correct_key,
                    explanation=f"Based on: {chosen_sent}",
                    source_chunk_ids=[chunk.id],
                    fingerprint=compute_prompt_fingerprint(chosen_prompt),
                    meta=meta,
                    unit=None,
                )
                candidates.append(cq)

            else:
                # short_answer (and numerical fallback)
                chosen_prompt = ""
                for t_idx, tmpl in enumerate(sa_templates):
                    cand_prompt = tmpl.format(concept_name=concept_name)
                    cand_fp = compute_prompt_fingerprint(cand_prompt)
                    if cand_fp not in do_not_repeat_fps and cand_fp not in batch_fps:
                        chosen_prompt = cand_prompt
                        break

                if not chosen_prompt:
                    chosen_prompt = sa_templates[q_idx % len(sa_templates)].format(concept_name=concept_name) + f" (Variant {q_idx + seed % 100})"

                batch_fps.add(compute_prompt_fingerprint(chosen_prompt))
                first_sent = sentences[0]
                model_answer = f"{concept_name} is defined as: {first_sent}"
                key_points = [
                    f"Accurate definition of {concept_name}",
                    f"Clear connection to: {first_sent[:50]}",
                ]
                meta = {
                    "key_points": key_points,
                    "model_answer": model_answer,
                    "verification": {"mode": "mock", "rule": "explanation"},
                }
                cq = CandidateQuestion(
                    topic_id=context.topic.id,
                    concept_id=concept_obj.id if concept_obj else None,
                    qtype="short_answer",
                    difficulty=diff,
                    prompt=chosen_prompt,
                    options=None,
                    correct_answer=model_answer,
                    explanation=f"Derived from: {first_sent}",
                    source_chunk_ids=[chunk.id],
                    fingerprint=compute_prompt_fingerprint(chosen_prompt),
                    meta=meta,
                    unit=None,
                )
                candidates.append(cq)

        return candidates


class LiveQuestionGenerator:
    """Live question generator calling Gemini API."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def generate_for_topic(
        self,
        context: TopicContext,
        do_not_repeat_prompts: List[str],
        seed: int,
    ) -> List[CandidateQuestion]:
        """Invoke Gemini to generate questions for a single topic."""
        settings = get_settings()
        if not context.chunks:
            return []

        sources_text = format_sources_for_prompt(context, settings.quiz_context_chars)
        concepts_list = ", ".join(c.name for c in context.concepts) if context.concepts else "None specified"
        do_not_repeat_text = (
            "\n".join(f"- {p}" for p in do_not_repeat_prompts[:15])
            if do_not_repeat_prompts
            else "None."
        )
        qtypes_list = ", ".join(context.assigned_qtypes)
        difficulty_label = ", ".join(context.assigned_difficulties)

        user_prompt = QUESTION_GENERATION_USER_PROMPT.format(
            num_questions=context.requested_count,
            topic_name=context.topic.name,
            topic_description=context.topic.description or "No description provided.",
            concepts_list=concepts_list,
            difficulty=difficulty_label,
            qtypes_list=qtypes_list,
            sources_text=sources_text,
            do_not_repeat_text=do_not_repeat_text,
        )

        try:
            llm_output: TopicGenerationLLMOutput = self.llm.generate_json(
                prompt=user_prompt,
                schema=TopicGenerationLLMOutput,
                system=QUESTION_GENERATION_SYSTEM_PROMPT,
                max_retries=2,
            )
        except Exception as exc:
            logger.warning("LLM generation failed for topic %s: %s", context.topic.id, exc)
            return []

        candidates: List[CandidateQuestion] = []
        for idx, gq in enumerate(llm_output.questions):
            # 1. Validate prompt
            clean_prompt = gq.prompt.strip()
            if not clean_prompt or len(clean_prompt) > 600:
                continue

            # 2. Map source chunk indices
            valid_chunk_ids: List[int] = []
            for src_idx in gq.used_sources:
                if 1 <= src_idx <= len(context.chunks):
                    valid_chunk_ids.append(context.chunks[src_idx - 1].id)
            # Remove duplicates preserving order
            valid_chunk_ids = list(dict.fromkeys(valid_chunk_ids))
            if not valid_chunk_ids:
                # If LLM didn't return valid indices, default to first chunk
                valid_chunk_ids = [context.chunks[0].id]

            # 3. Resolve concept id
            concept_id = map_concept_name_to_id(gq.concept_name, context.concepts)

            # 4. Handle MCQ options
            qtype = gq.qtype.lower()
            if qtype not in {"mcq", "short_answer", "numerical"}:
                qtype = "short_answer"

            difficulty = gq.difficulty.lower()
            if difficulty not in {"easy", "medium", "hard"}:
                difficulty = "medium"

            meta: Dict[str, Any] = {}
            options: Optional[List[Dict[str, str]]] = None
            correct_answer = ""
            unit_label: Optional[str] = None

            if qtype == "mcq":
                processed = process_mcq_options(gq.options, gq.correct_option_index, seed + idx * 31)
                if not processed:
                    continue
                options, correct_answer = processed

            elif qtype == "numerical":
                if gq.numerical_answer is None:
                    # Fallback to short answer if numeric answer missing
                    qtype = "short_answer"
                    correct_answer = gq.model_answer or clean_prompt
                    meta["key_points"] = gq.key_points or [correct_answer[:60]]
                else:
                    correct_answer = str(gq.numerical_answer)
                    unit_label = gq.unit
                    meta["tolerance_pct"] = gq.tolerance_pct or 5.0
                    meta["unit"] = gq.unit
                    meta["numerical_answer"] = gq.numerical_answer

            if qtype == "short_answer":
                correct_answer = gq.model_answer or "Model answer based on source text."
                meta["key_points"] = gq.key_points or [correct_answer[:60]]

            explanation = gq.explanation.strip() or f"Supported by course source excerpt."
            fp = compute_prompt_fingerprint(clean_prompt)

            candidates.append(
                CandidateQuestion(
                    topic_id=context.topic.id,
                    concept_id=concept_id,
                    qtype=qtype,
                    difficulty=difficulty,
                    prompt=clean_prompt,
                    options=options,
                    correct_answer=correct_answer,
                    explanation=explanation,
                    source_chunk_ids=valid_chunk_ids,
                    fingerprint=fp,
                    meta=meta,
                    unit=unit_label,
                )
            )

        return candidates
