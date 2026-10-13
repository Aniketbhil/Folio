from typing import List
from pydantic import BaseModel, Field


# 1. MAP stage schema
class CandidateTopic(BaseModel):
    name: str = Field(..., description="Subject-matter topic name")
    description: str = Field(..., description="Brief 1-2 sentence description")


class MapTopicsOutput(BaseModel):
    topics: List[CandidateTopic] = Field(default_factory=list, description="Extracted candidate topics")


# 2. REDUCE stage schema
class SubtopicOutput(BaseModel):
    name: str = Field(..., description="Subtopic (leaf topic) name")
    description: str = Field(..., description="Factual 1-2 sentence description")
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Names of other subtopics that directly precede this topic (max 3)",
    )
    teaching_order: int = Field(default=0, description="Recommended sequence index")


class TopTopicOutput(BaseModel):
    name: str = Field(..., description="Top-level parent topic category")
    description: str = Field(default="", description="High-level description of category")
    subtopics: List[SubtopicOutput] = Field(
        default_factory=list,
        description="Constituent subtopics",
    )


class TaxonomyOutput(BaseModel):
    topics: List[TopTopicOutput] = Field(
        default_factory=list,
        description="Complete course syllabus taxonomy",
    )


# 3. TAG stage schema
class ChunkTopicAssignment(BaseModel):
    name: str = Field(..., description="Assigned leaf topic name")
    relevance: float = Field(default=1.0, description="Relevance score between 0.0 and 1.0")


class ChunkConceptExtraction(BaseModel):
    name: str = Field(..., description="Key concept or technical term")
    definition: str = Field(..., description="Concise definition from material")
    topic_name: str = Field(..., description="Matching leaf topic name")


class ChunkTagItem(BaseModel):
    chunk_id: int = Field(..., description="ID of chunk being tagged")
    topics: List[ChunkTopicAssignment] = Field(default_factory=list, description="1-3 assigned leaf topics")
    concepts: List[ChunkConceptExtraction] = Field(default_factory=list, description="Up to 4 extracted concepts")


class TagBatchOutput(BaseModel):
    chunks: List[ChunkTagItem] = Field(default_factory=list, description="Tagging results for chunk batch")
