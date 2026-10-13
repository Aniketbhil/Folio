from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class Citation(BaseModel):
    """Reusable citation reference to an ingested source text chunk."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    source_id: int
    source_title: str
    source_type: str  # "pdf" | "slide" | "video"
    location: Dict[str, Any]
    section_title: Optional[str] = None
    snippet: str
    score: Optional[float] = None
    open_url: str
