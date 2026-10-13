"""Assessment question verification (live LLM with blind-solve and mock verifier)."""

import logging
import re
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.models.source import Chunk
from app.services.assessment.prompts import (
    TOPIC_VERIFICATION_SYSTEM_PROMPT,
    TOPIC_VERIFICATION_USER_PROMPT,
)
from app.services.assessment.schemas import (
    CandidateQuestion,
    QuestionVerificationItemLLM,
    TopicVerificationLLMOutput,
)
from app.services.assessment.selection import TopicContext
from app.services.llm import LLMClient, get_llm_client

logger = logging.getLogger(__name__)


class MockQuestionVerifier:
    """Deterministic verification for offline testing without LLM calls."""

    def verify_candidates(
        self,
        candidates: List[CandidateQuestion],
        chunk_map: Dict[int, Chunk],
    ) -> Tuple[List[CandidateQuestion], List[Dict[str, str]]]:
        """Verify candidate questions using deterministic source matching rules.

        - MCQ: Passes if the text of the correct option appears in the cited chunk text.
        - Short Answer: Passes if the model answer is a substring of or overlaps >= 50% with cited chunk text.
        """
        verified: List[CandidateQuestion] = []
        rejected: List[Dict[str, str]] = []

        for cq in candidates:
            # Combine cited chunk texts
            cited_text = " ".join(
                chunk_map[cid].text.lower()
                for cid in cq.source_chunk_ids
                if cid in chunk_map
            )
            if not cited_text:
                rejected.append({
                    "prompt": cq.prompt[:120],
                    "reason": "No cited chunk content available to verify",
                })
                continue

            if cq.qtype == "mcq":
                # Find the text corresponding to correct_answer key (A, B, C, D)
                correct_opt_text = ""
                if cq.options:
                    for opt in cq.options:
                        if opt["key"] == cq.correct_answer:
                            correct_opt_text = opt["text"].strip().lower()
                            break

                if not correct_opt_text:
                    rejected.append({
                        "prompt": cq.prompt[:120],
                        "reason": f"Correct option key '{cq.correct_answer}' not found in options",
                    })
                    continue

                # Check if correct option text appears in cited text
                clean_opt = re.sub(r"[^a-zA-Z0-9\s]", "", correct_opt_text)
                clean_chunk = re.sub(r"[^a-zA-Z0-9\s]", "", cited_text)

                if clean_opt in clean_chunk or any(w in clean_chunk for w in clean_opt.split() if len(w) > 3):
                    cq.verified = True
                    cq.verification_notes = f"(mock) Verified: option text '{correct_opt_text[:30]}' supported by source"
                    verified.append(cq)
                else:
                    rejected.append({
                        "prompt": cq.prompt[:120],
                        "reason": f"Correct option text '{correct_opt_text[:40]}' not substantiated in cited source",
                    })

            else:
                # Short answer / numerical
                target_ans = cq.correct_answer.strip().lower()
                clean_target = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", target_ans))
                chunk_words = set(re.findall(r"\b[a-zA-Z0-9]{3,}\b", cited_text))

                if not clean_target:
                    cq.verified = True
                    cq.verification_notes = "(mock) Verified short answer"
                    verified.append(cq)
                    continue

                overlap = len(clean_target.intersection(chunk_words)) / len(clean_target)
                if overlap >= 0.50 or target_ans in cited_text:
                    cq.verified = True
                    cq.verification_notes = f"(mock) Verified: model answer has {overlap*100:.1f}% lexical overlap with source"
                    verified.append(cq)
                else:
                    rejected.append({
                        "prompt": cq.prompt[:120],
                        "reason": f"Model answer has insufficient overlap ({overlap*100:.1f}% < 50%) with cited source",
                    })

        return verified, rejected


class LiveQuestionVerifier:
    """Live verification using LLM (blind-solve for MCQ, rubric check for free-response)."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    def verify_candidates(
        self,
        candidates: List[CandidateQuestion],
        chunk_map: Dict[int, Chunk],
    ) -> Tuple[List[CandidateQuestion], List[Dict[str, str]]]:
        """Verify candidate questions using structured cross-model verification."""
        settings = get_settings()
        verify_model = settings.verify_model if settings.verify_model else None

        verified: List[CandidateQuestion] = []
        rejected: List[Dict[str, str]] = []

        if not candidates:
            return [], []

        # 1. Format cited sources
        all_cited_chunk_ids = list(dict.fromkeys(cid for cq in candidates for cid in cq.source_chunk_ids))
        sources_blocks: List[str] = []
        for idx, cid in enumerate(all_cited_chunk_ids, start=1):
            chunk = chunk_map.get(cid)
            if chunk:
                sources_blocks.append(f"[{idx}] (Chunk {chunk.id}):\n{chunk.text[: settings.quiz_context_chars]}")
        sources_text = "\n\n".join(sources_blocks)

        # 2. Format questions to verify
        questions_blocks: List[str] = []
        for idx, cq in enumerate(candidates):
            if cq.qtype == "mcq":
                opts_str = "\n".join(f"  ({i}) {opt['text']}" for i, opt in enumerate(cq.options or []))
                q_text = (
                    f"Question {idx} (MCQ):\n"
                    f"Prompt: {cq.prompt}\n"
                    f"Options (blind solve - do not see key):\n{opts_str}\n"
                )
            elif cq.qtype == "numerical":
                q_text = (
                    f"Question {idx} (Numerical):\n"
                    f"Prompt: {cq.prompt}\n"
                    f"Target Value: {cq.correct_answer} {cq.unit or ''}\n"
                    f"Tolerance: {cq.meta.get('tolerance_pct', 5.0)}%\n"
                )
            else:
                q_text = (
                    f"Question {idx} (Short Answer):\n"
                    f"Prompt: {cq.prompt}\n"
                    f"Model Answer: {cq.correct_answer}\n"
                    f"Key Points: {cq.meta.get('key_points', [])}\n"
                )
            questions_blocks.append(q_text)

        user_prompt = TOPIC_VERIFICATION_USER_PROMPT.format(
            sources_text=sources_text,
            questions_text="\n\n".join(questions_blocks),
        )

        try:
            llm_result: TopicVerificationLLMOutput = self.llm.generate_json(
                prompt=user_prompt,
                schema=TopicVerificationLLMOutput,
                system=TOPIC_VERIFICATION_SYSTEM_PROMPT,
                max_retries=2,
                model=verify_model,
            )
            eval_map = {res.question_index: res for res in llm_result.results}
        except Exception as exc:
            logger.warning("Live verification call failed: %s", exc)
            eval_map = {}

        # 3. Evaluate each candidate against verification response
        for idx, cq in enumerate(candidates):
            eval_item = eval_map.get(idx)
            if not eval_item:
                rejected.append({
                    "prompt": cq.prompt[:120],
                    "reason": "Verification failed to produce structured assessment for question",
                })
                continue

            if cq.qtype == "mcq":
                # Blind solve evaluation
                # Map chosen_option_index to key ('A', 'B', 'C', 'D')
                chosen_idx = eval_item.chosen_option_index
                chosen_key = None
                if chosen_idx is not None and cq.options and 0 <= chosen_idx < len(cq.options):
                    chosen_key = cq.options[chosen_idx]["key"]

                conf = eval_item.confidence or 0.0
                if (
                    chosen_key == cq.correct_answer
                    and eval_item.supported
                    and conf >= 0.60
                ):
                    cq.verified = True
                    cq.verification_notes = f"Blind-solve matched key '{chosen_key}' with confidence {conf:.2f}"
                    verified.append(cq)
                else:
                    reasons = []
                    if chosen_key != cq.correct_answer:
                        reasons.append(f"verifier chose '{chosen_key}' vs key '{cq.correct_answer}'")
                    if not eval_item.supported:
                        reasons.append("source does not support answer")
                    if conf < 0.60:
                        reasons.append(f"confidence {conf:.2f} < 0.60")
                    rejected.append({
                        "prompt": cq.prompt[:120],
                        "reason": "; ".join(reasons) or "MCQ verification failed",
                    })

            else:
                # Short Answer / Numerical
                if eval_item.supported and eval_item.key_correct and not eval_item.ambiguous:
                    cq.verified = True
                    cq.verification_notes = eval_item.notes or "Model answer and rubric confirmed accurate"
                    verified.append(cq)
                else:
                    reasons = []
                    if not eval_item.supported:
                        reasons.append("unsupported by source")
                    if not eval_item.key_correct:
                        reasons.append("answer key deemed incorrect")
                    if eval_item.ambiguous:
                        reasons.append("question stem is ambiguous")
                    rejected.append({
                        "prompt": cq.prompt[:120],
                        "reason": "; ".join(reasons) or "Free-response verification failed",
                    })

        return verified, rejected
