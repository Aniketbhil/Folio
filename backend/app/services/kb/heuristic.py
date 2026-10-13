from collections import Counter
import re
from typing import Dict, List, Optional, Tuple

from app.models.source import Chunk, Source
from app.services.kb.schemas import (
    ChunkConceptExtraction,
    ChunkTagItem,
    ChunkTopicAssignment,
    SubtopicOutput,
    TaxonomyOutput,
    TopTopicOutput,
)

STOPWORDS = {
    "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "as", "is", "are", "was", "were", "it", "this", "that", "these",
    "those", "then", "there", "when", "where", "which", "who", "what", "how", "why", "all", "each",
    "first", "second", "third", "part", "lecture", "slide", "page",
}


def _extract_first_sentence(text: str) -> str:
    """Extract the first coherent sentence from text."""
    clean = re.sub(r"\s+", " ", text).strip()
    match = re.search(r"([^.!?]+[.!?])", clean)
    if match:
        return match.group(1).strip()
    return (clean[:120] + "...").strip()


def _find_top_concepts(
    chunks: List[Chunk],
    max_concepts: int = 3,
) -> List[Tuple[str, str]]:
    """Extract up to max_concepts terms and their defining sentences using frequency analysis."""
    combined_text = " ".join(c.text for c in chunks)
    # Find capitalized words or multi-word terms
    matches = re.findall(r"\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b", combined_text)

    counts = Counter()
    for m in matches:
        term = m.strip()
        words = [w.lower() for w in term.split()]
        if len(term) >= 3 and not all(w in STOPWORDS for w in words):
            counts[term] += 1

    top_terms = [t for t, _ in counts.most_common(max_concepts * 2)]
    results: List[Tuple[str, str]] = []

    # Find definition sentence for each term
    sentences = re.split(r"(?<=[.!?])\s+", combined_text)
    for term in top_terms:
        if len(results) >= max_concepts:
            break
        term_pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
        for s in sentences:
            if term_pattern.search(s):
                clean_s = re.sub(r"\s+", " ", s).strip()
                if len(clean_s) >= 15:
                    results.append((term, clean_s))
                    break

    return results


class HeuristicKBBuilder:
    """Heuristic knowledge base taxonomy and tagging generator used in LLM_MOCK mode."""

    def build(
        self,
        chunks: List[Chunk],
        sources: Dict[int, Source],
    ) -> Tuple[TaxonomyOutput, List[ChunkTagItem]]:
        """Synthesize curriculum taxonomy and chunk tags using deterministic structural heuristics."""
        if not chunks:
            return TaxonomyOutput(topics=[]), []

        # 1. Group chunks by source
        chunks_by_source: Dict[int, List[Chunk]] = {}
        for c in chunks:
            chunks_by_source.setdefault(c.source_id, []).append(c)

        top_topics: List[TopTopicOutput] = []
        tag_items: List[ChunkTagItem] = []
        chunk_tags_map: Dict[int, ChunkTagItem] = {
            c.id: ChunkTagItem(chunk_id=c.id, topics=[], concepts=[]) for c in chunks
        }

        for source_id, src_chunks in chunks_by_source.items():
            source = sources.get(source_id)
            source_title = source.title if source else f"Source {source_id}"

            # Group chunks into sub-groups by section_title or 5-chunk window
            group_order: List[str] = []
            grouped_chunks: Dict[str, List[Chunk]] = {}

            for idx, c in enumerate(src_chunks):
                if c.section_title and c.section_title.strip():
                    key = c.section_title.strip()
                else:
                    window_num = (idx // 3) + 1
                    key = f"{source_title} - Part {window_num}"

                if key not in grouped_chunks:
                    grouped_chunks[key] = []
                    group_order.append(key)
                grouped_chunks[key].append(c)

            # If all groups have 1 chunk (e.g. distinct slide/section titles), preserve them so subtopics and prerequisites exist
            if len(group_order) > 1 and all(len(grouped_chunks[k]) == 1 for k in group_order):
                consolidated_order = list(group_order)
                consolidated_chunks = dict(grouped_chunks)
            else:
                consolidated_order = []
                consolidated_chunks = {}
                for key in group_order:
                    g_chunks = grouped_chunks[key]
                    if len(g_chunks) == 1 and len(consolidated_order) >= 2:
                        last_key = consolidated_order[-1]
                        consolidated_chunks[last_key].extend(g_chunks)
                    else:
                        consolidated_order.append(key)
                        consolidated_chunks[key] = list(g_chunks)

            # Build subtopics for this top-level topic
            subtopics: List[SubtopicOutput] = []
            prev_subtopic_name: Optional[str] = None

            for order_idx, key in enumerate(consolidated_order):
                g_chunks = consolidated_chunks[key]
                first_text = g_chunks[0].text if g_chunks else ""
                desc = _extract_first_sentence(first_text)

                prereqs = [prev_subtopic_name] if prev_subtopic_name else []
                subtopics.append(
                    SubtopicOutput(
                        name=key,
                        description=desc,
                        prerequisites=prereqs,
                        teaching_order=order_idx + 1,
                    )
                )

                # Extract concepts for this subtopic
                concepts = _find_top_concepts(g_chunks, max_concepts=3)

                # Tag each chunk in this group
                for c in g_chunks:
                    chunk_tags_map[c.id].topics.append(
                        ChunkTopicAssignment(name=key, relevance=1.0)
                    )
                    for c_name, c_def in concepts:
                        if c_name.lower() in c.text.lower():
                            chunk_tags_map[c.id].concepts.append(
                                ChunkConceptExtraction(
                                    name=c_name,
                                    definition=c_def,
                                    topic_name=key,
                                )
                            )

                prev_subtopic_name = key

            top_topics.append(
                TopTopicOutput(
                    name=source_title,
                    description=f"Course concepts and materials from {source_title}.",
                    subtopics=subtopics,
                )
            )

        tag_items = list(chunk_tags_map.values())
        return TaxonomyOutput(topics=top_topics), tag_items
