import math
import re
from typing import Any, Dict, List

from app.services.ingestion.parsers.base import ParsedUnit


def estimate_tokens(text: str) -> int:
    """Heuristic token estimation: ceil(words * 1.3). No external tokenizer required."""
    words = len(text.split())
    return math.ceil(words * 1.3)


def split_text_with_overlap(
    text: str,
    target_tokens: int = 400,
    overlap_tokens: int = 50,
) -> List[str]:
    """Split long text along paragraph then sentence boundaries near target_tokens with overlap."""
    text = text.strip()
    if not text:
        return []

    # First divide by paragraphs
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    # Split paragraphs into sentences if needed
    sentences: List[str] = []
    for para in paragraphs:
        para_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", para) if s.strip()]
        if para_sentences:
            sentences.extend(para_sentences)
        else:
            sentences.append(para)

    chunks: List[str] = []
    current_sentences: List[str] = []

    for sentence in sentences:
        current_sentences.append(sentence)
        current_text = " ".join(current_sentences)
        if estimate_tokens(current_text) >= target_tokens:
            chunks.append(current_text.strip())

            # Carry over trailing sentences for overlap
            overlap_sentences: List[str] = []
            for back_s in reversed(current_sentences):
                overlap_sentences.insert(0, back_s)
                if estimate_tokens(" ".join(overlap_sentences)) >= overlap_tokens:
                    break
            current_sentences = overlap_sentences

    # Flush remainder if not redundant
    if current_sentences:
        remainder_text = " ".join(current_sentences).strip()
        if not chunks or remainder_text != chunks[-1]:
            chunks.append(remainder_text)

    return [c for c in chunks if c.strip()]


def create_chunks_from_units(
    units: List[ParsedUnit],
    target_tokens: int = 400,
    overlap_tokens: int = 50,
) -> List[Dict[str, Any]]:
    """Transform parsed units into sequential, non-empty database chunk dictionaries."""
    raw_chunks: List[Dict[str, Any]] = []

    for unit in units:
        clean_text = unit.text.strip()
        if not clean_text:
            continue

        token_len = estimate_tokens(clean_text)
        threshold = int(target_tokens * 1.5)

        if unit.source_type == "pdf":
            # PDF pages: keep together unless significantly exceeding threshold
            if token_len <= threshold:
                pieces = [clean_text]
            else:
                pieces = split_text_with_overlap(clean_text, target_tokens, overlap_tokens)

            for piece in pieces:
                if piece.strip():
                    raw_chunks.append({
                        "text": piece.strip(),
                        "source_type": "pdf",
                        "page_number": unit.page_number,
                        "slide_number": None,
                        "start_sec": None,
                        "end_sec": None,
                        "section_title": unit.section_title,
                    })

        elif unit.source_type == "slide":
            # Slides: keep slide intact unless significantly exceeding threshold
            if token_len <= threshold:
                pieces = [clean_text]
            else:
                pieces = split_text_with_overlap(clean_text, target_tokens, overlap_tokens)

            for piece in pieces:
                if piece.strip():
                    raw_chunks.append({
                        "text": piece.strip(),
                        "source_type": "slide",
                        "page_number": None,
                        "slide_number": unit.slide_number,
                        "start_sec": None,
                        "end_sec": None,
                        "section_title": unit.section_title,
                    })

        elif unit.source_type == "video":
            # Transcripts: if already timed windows, maintain them; if untimed text, split if needed
            if unit.start_sec is not None:
                raw_chunks.append({
                    "text": clean_text,
                    "source_type": "video",
                    "page_number": None,
                    "slide_number": None,
                    "start_sec": unit.start_sec,
                    "end_sec": unit.end_sec,
                    "section_title": unit.section_title,
                })
            else:
                if token_len <= threshold:
                    pieces = [clean_text]
                else:
                    pieces = split_text_with_overlap(clean_text, target_tokens, overlap_tokens)

                for piece in pieces:
                    if piece.strip():
                        raw_chunks.append({
                            "text": piece.strip(),
                            "source_type": "video",
                            "page_number": None,
                            "slide_number": None,
                            "start_sec": None,
                            "end_sec": None,
                            "section_title": unit.section_title,
                        })

    # Sequentially index and calculate token counts
    indexed_chunks: List[Dict[str, Any]] = []
    for idx, c in enumerate(raw_chunks):
        indexed_chunks.append({
            "chunk_index": idx,
            "text": c["text"],
            "source_type": c["source_type"],
            "page_number": c["page_number"],
            "slide_number": c["slide_number"],
            "start_sec": c["start_sec"],
            "end_sec": c["end_sec"],
            "section_title": c["section_title"],
            "token_count": estimate_tokens(c["text"]),
            "embedded": False,
        })

    return indexed_chunks
