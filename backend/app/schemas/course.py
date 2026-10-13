from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CourseCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Course name")
    description: Optional[str] = Field(None, description="Course syllabus/description")


class CourseCounts(BaseModel):
    sources: int = 0
    chunks: int = 0
    topics: int = 0
    concepts: int = 0


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    kb_status: str
    created_at: datetime


class CourseDetailRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    kb_status: str
    created_at: datetime
    counts: CourseCounts


class CourseDeleteResponse(BaseModel):
    deleted: bool
