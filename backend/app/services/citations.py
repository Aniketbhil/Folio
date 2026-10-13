import re
from typing import Optional

from app.core.config import get_settings
from app.models.source import Chunk, Source
from app.schemas.citation import Citation


def _make_snippet(text: str, max_chars: int) -> str:
    """Extract snippet up to max_chars, truncated at a word boundary with trailing ellipsis."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned

    truncated = cleaned[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:- ") + "..."


def build_citation(
    chunk: Chunk,
    source: Source,
    score: Optional[float] = None,
    snippet_chars: Optional[int] = None,
) -> Citation:
    """Build a standardized Citation object for a text chunk and its parent source."""
    if snippet_chars is None:
        snippet_chars = get_settings().snippet_chars

    if chunk.source_type == "pdf":
        location = {"page": chunk.page_number}
    elif chunk.source_type == "slide":
        location = {"slide": chunk.slide_number}
    elif chunk.source_type == "video":
        location = {"start_sec": chunk.start_sec, "end_sec": chunk.end_sec}
    else:
        location = {}

    snippet = _make_snippet(chunk.text, snippet_chars)
    open_url = f"/api/v1/chunks/{chunk.id}"

    return Citation(
        chunk_id=chunk.id,
        source_id=source.id,
        source_title=source.title,
        source_type=chunk.source_type,
        location=location,
        section_title=chunk.section_title,
        snippet=snippet,
        score=round(score, 4) if score is not None else None,
        open_url=open_url,
    )
