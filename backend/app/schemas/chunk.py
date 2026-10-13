from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ChunkViewerChunk(BaseModel):
    id: int
    chunk_index: int
    text: str
    token_count: int
    source_type: str
    location: Any
    section_title: Optional[str] = None


class ChunkViewerSource(BaseModel):
    id: int
    title: str
    source_type: str
    original_filename: str
    status: str


class ChunkViewerInfo(BaseModel):
    kind: str  # "pdf_page" | "slide" | "video_time" | "text"
    page: Optional[int] = None
    slide: Optional[int] = None
    start_sec: Optional[float] = None
    end_sec: Optional[float] = None
    has_timestamps: bool = False


class ChunkNeighbor(BaseModel):
    id: int
    location: Any
    preview: str


class ChunkTopicBrief(BaseModel):
    id: int
    name: str
    relevance: float


class ChunkConceptBrief(BaseModel):
    id: int
    name: str


class ChunkViewerResponse(BaseModel):
    chunk: ChunkViewerChunk
    source: ChunkViewerSource
    file_url: str
    viewer: ChunkViewerInfo
    media_url: Optional[str] = None
    seek_url: Optional[str] = None
    previous: Optional[ChunkNeighbor] = None
    next: Optional[ChunkNeighbor] = None
    topics: List[ChunkTopicBrief] = []
    concepts: List[ChunkConceptBrief] = []


ChunkDetail = ChunkViewerChunk
ChunkSourceDetail = ChunkViewerSource
ChunkViewer = ChunkViewerInfo

