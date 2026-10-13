from typing import Any, List, Optional
from pydantic import BaseModel, Field


class LLMTestRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Prompt to send to LLM")


class LLMTestResponse(BaseModel):
    mode: str
    output: str


class EmbedTestRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, description="List of texts to embed")


class EmbedTestResponse(BaseModel):
    dim: int
    count: int


class VectorTestResultItem(BaseModel):
    chunk_id: int
    score: float
    distance: float


class VectorTestResponse(BaseModel):
    success: bool
    queried_chunks: List[VectorTestResultItem]
    cleaned_up: bool


class DevIntegrityDetails(BaseModel):
    orphan_vectors: List[int]
    chunks_not_embedded: List[int]
    vectors_missing_for_embedded_chunks: List[int]
    topics_without_chunks: List[int]
    sources_ready_without_chunks: List[int]
    questions_without_vectors: List[int]
    stuck_sources: List[int]
    stuck_courses: List[int]


class DevIntegrityResponse(BaseModel):
    clean: bool
    issues: DevIntegrityDetails
    fixed: Optional[dict] = None
