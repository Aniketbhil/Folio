from typing import Any, List
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
