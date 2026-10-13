from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class StudentCreate(BaseModel):
    name: str = Field(..., min_length=1, description="Student display name")


class StudentCourseActivityOut(BaseModel):
    course_id: int
    course_name: str
    average_mastery: Optional[float] = None
    last_active_at: Optional[datetime] = None


class StudentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    courses_with_activity: Optional[list[StudentCourseActivityOut]] = None
