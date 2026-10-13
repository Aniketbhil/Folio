from pydantic import BaseModel


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class HealthCounts(BaseModel):
    students: int
    courses: int
    sources: int
    chunks: int


class HealthResponse(BaseModel):
    status: str
    db: str
    vector_store: str
    llm_mode: str
    version: str
    uptime_sec: float
    counts: HealthCounts
    kb_building_courses: int
    ingestion_active: int
