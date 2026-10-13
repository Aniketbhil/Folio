from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class SourceRead(BaseModel):
    """Pydantic representation of a course source document."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: int
    title: str
    source_type: str
    original_filename: str
    file_path: str
    status: str
    stage: Optional[str] = None
    progress: int = 0
    error: Optional[str] = None
    num_units: int = 0
    meta: Dict[str, Any] = {}
    created_at: datetime
    chunk_count: int = 0


class ChunkRead(BaseModel):
    """Pydantic representation of an extracted text chunk."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    chunk_index: int
    source_type: str
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    section_title: Optional[str] = None
    token_count: int
    text: str


class SourceDeleteResponse(BaseModel):
    """Response returned upon successful source deletion."""

    deleted: bool
