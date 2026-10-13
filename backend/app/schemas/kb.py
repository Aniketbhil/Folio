from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.citation import Citation


class KBStatusCounts(BaseModel):
    topics: int = 0
    leaf_topics: int = 0
    concepts: int = 0
    total_chunks: int = 0
    tagged_chunks: int = 0
    untagged_chunks: int = 0
    prerequisites: int = 0


class KBStatusResponse(BaseModel):
    kb_status: str
    kb_error: Optional[str] = None
    kb_built_at: Optional[datetime] = None
    stage: str
    progress: int
    counts: KBStatusCounts


class KBRebuildResponse(BaseModel):
    kb_status: str = "building"


class TopicTreeNode(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    order_index: int
    parent_id: Optional[int] = None
    is_leaf: bool
    chunk_count: int
    concept_count: int
    children: List["TopicTreeNode"] = []


class ConceptItem(BaseModel):
    id: int
    name: str
    definition: str
    topic_id: int
    topic_name: str


class TopicBrief(BaseModel):
    id: int
    name: str


class ConceptBrief(BaseModel):
    id: int
    name: str
    definition: str


class TopicDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    parent: Optional[TopicBrief] = None
    children: List[TopicBrief] = []
    concepts: List[ConceptBrief] = []
    prerequisites: List[TopicBrief] = []
    unlocks: List[TopicBrief] = []
    chunk_count: int
    chunks: List[Citation] = []


class GraphNode(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    level: int  # 0: root, 1: leaf
    is_leaf: bool
    chunk_count: int


class GraphEdge(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: int = Field(..., alias="from")
    to: int


class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
