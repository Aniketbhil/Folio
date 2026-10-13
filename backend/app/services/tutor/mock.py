import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.models.source import Chunk, Source
from app.services.kb.heuristic import STOPWORDS, _extract_first_sentence
from app.services.retrieval import RetrievedChunk
from app.services.tutor.schemas import TutorLLMOutput

FOLLOWUP_KEYWORDS = {"it", "that", "this", "they", "why", "explain more", "and", "more", "again"}


def is_followup_message(content: str) -> bool:
    """Detect whether a student message appears to be a follow-up question."""
    lowered = content.strip().lower()
    words = set(re.findall(r"\b[a-z0-9_]+\b", lowered))
    if len(content.strip().split()) <= 4:
        return True
    if words.intersection(FOLLOWUP_KEYWORDS):
        return True
    if lowered.startswith("and ") or lowered.startswith("why "):
        return True
    return False


class MockTutor:
    """Mock implementation of the tutor logic for test and offline environments."""

    def rewrite_query(self, history: List[Dict[str, str]], query: str) -> str:
        """Deterministically simulate query rewriting using conversation history."""
        last_user_msg = ""
        for m in reversed(history):
            if m.get("role") == "user":
                last_user_msg = m.get("content", "").strip()
                break

        if last_user_msg:
            # Clean last user question of punctuation
            clean_prior = re.sub(r"[?!.]", "", last_user_msg).strip()
            return f"{query} regarding {clean_prior}"
        return query

    def evaluate_grounding(
        self,
        query: str,
        retrieved: List[RetrievedChunk],
    ) -> Tuple[str, float, List[int]]:
        """Calculate lexical overlap across retrieved chunks to determine grounding status."""
        settings = get_settings()
        words = re.findall(r"\b[a-zA-Z0-9]+\b", query.lower())
        query_terms = [w for w in words if w not in STOPWORDS and len(w) > 2]
        if not query_terms:
            query_terms = [w for w in words if len(w) > 1]
        if not query_terms:
            return "unsupported", 0.0, []

        best_overlap = 0.0
        matching_indices: List[int] = []

        for idx, item in enumerate(retrieved, start=1):
            text_lower = item.chunk.text.lower()
            matches = sum(1 for term in query_terms if term in text_lower)
            overlap = matches / len(query_terms)
            if overlap > 0.0:
                matching_indices.append(idx)
            if overlap > best_overlap:
                best_overlap = overlap

        if best_overlap >= 0.60:
            status = "grounded"
        elif best_overlap >= settings.tutor_mock_min_overlap:
            status = "partial"
        else:
            status = "unsupported"

        return status, best_overlap, matching_indices

    def generate_answer(
        self,
        query: str,
        retrieved: List[RetrievedChunk],
        grounding: str,
        used_indices: List[int],
        related_topic_names: List[str],
    ) -> TutorLLMOutput:
        """Produce deterministic mock answer conforming to the live LLM schema."""
        if grounding == "unsupported" or not used_indices:
            followups = [f"Explain {t}" for t in related_topic_names[:3]]
            return TutorLLMOutput(
                grounding="unsupported",
                answer="I couldn't find this in your course material.",
                used_sources=[],
                outside_knowledge_note=None,
                followups=followups,
            )

        # Select up to top 2 matching chunks
        selected_indices = used_indices[:2]
        answer_parts: List[str] = []

        for marker_idx, source_idx in enumerate(selected_indices, start=1):
            chunk = retrieved[source_idx - 1].chunk
            first_sent = _extract_first_sentence(chunk.text)
            answer_parts.append(f"{first_sent} [{source_idx}]")

        answer_text = " ".join(answer_parts)
        outside_note: Optional[str] = None

        if grounding == "partial":
            answer_text += "\n\nOutside your material:\n(mock) general explanation would go here."
            outside_note = "General concepts not fully detailed in your course material."

        followups = [f"Explain {t}" for t in related_topic_names[:3]]

        return TutorLLMOutput(
            grounding=grounding,
            answer=answer_text,
            used_sources=selected_indices,
            outside_knowledge_note=outside_note,
            followups=followups,
        )
