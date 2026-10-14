from typing import Any, Dict, List, Optional, Set
from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.course import Course
from app.models.source import Chunk, Source
from app.models.topic import ChunkTopic, Concept, Topic, TopicPrereq
from app.schemas.citation import Citation
from app.schemas.kb import (
    ConceptBrief,
    ConceptItem,
    GraphEdge,
    GraphNode,
    GraphResponse,
    KBRebuildResponse,
    KBStatusCounts,
    KBStatusResponse,
    TopicBrief,
    TopicDetailResponse,
    TopicTreeNode,
)
from app.services.auth.dependencies import get_current_student
from app.services.citations import build_citation
from app.services.kb.service import get_kb_service

router = APIRouter(tags=["knowledge-base"], dependencies=[Depends(get_current_student)])


@router.get("/courses/{course_id}/kb/status", response_model=KBStatusResponse)
def get_course_kb_status(
    course_id: int,
    db: Session = Depends(get_db),
) -> KBStatusResponse:
    """Get knowledge base build status, progress, and entity counts."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    # Calculate status counts
    total_topics = (
        db.scalar(select(func.count(Topic.id)).where(Topic.course_id == course_id))
        or 0
    )

    parent_ids_subq = (
        select(Topic.parent_id)
        .where(Topic.course_id == course_id, Topic.parent_id.is_not(None))
        .distinct()
    )
    leaf_topics = (
        db.scalar(
            select(func.count(Topic.id)).where(
                Topic.course_id == course_id,
                Topic.id.not_in(parent_ids_subq),
            )
        )
        or 0
    )

    concepts = (
        db.scalar(
            select(func.count(Concept.id)).where(Concept.course_id == course_id)
        )
        or 0
    )

    total_chunks = (
        db.scalar(select(func.count(Chunk.id)).where(Chunk.course_id == course_id))
        or 0
    )

    tagged_chunks = (
        db.scalar(
            select(func.count(distinct(ChunkTopic.chunk_id)))
            .join(Chunk, Chunk.id == ChunkTopic.chunk_id)
            .where(Chunk.course_id == course_id)
        )
        or 0
    )

    untagged_chunks = max(0, total_chunks - tagged_chunks)

    prerequisites = (
        db.scalar(
            select(func.count(TopicPrereq.topic_id)).where(
                TopicPrereq.course_id == course_id
            )
        )
        or 0
    )

    counts = KBStatusCounts(
        topics=total_topics,
        leaf_topics=leaf_topics,
        concepts=concepts,
        total_chunks=total_chunks,
        tagged_chunks=tagged_chunks,
        untagged_chunks=untagged_chunks,
        prerequisites=prerequisites,
    )

    kb_svc = get_kb_service()
    prog = kb_svc.get_progress(course_id)
    stage = prog["stage"]
    progress_val = prog["progress"]

    if course.kb_status == "ready" and not kb_svc.is_building(course_id):
        stage = "ready"
        progress_val = 100
    elif course.kb_status == "empty" and not kb_svc.is_building(course_id):
        stage = "empty"
        progress_val = 0

    return KBStatusResponse(
        kb_status=course.kb_status,
        kb_error=course.kb_error,
        kb_built_at=course.kb_built_at,
        stage=stage,
        progress=progress_val,
        counts=counts,
    )


@router.post(
    "/courses/{course_id}/kb/rebuild",
    response_model=KBRebuildResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def rebuild_course_kb(
    course_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> KBRebuildResponse:
    """Trigger an asynchronous rebuild of the knowledge base for a course."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    kb_svc = get_kb_service()
    if course.kb_status == "building" or kb_svc.is_building(course_id):
        raise AppError(
            "Knowledge base build is already in progress",
            code="kb_busy",
            status_code=409,
        )

    ready_sources = (
        db.scalar(
            select(func.count(Source.id)).where(
                Source.course_id == course_id, Source.status == "ready"
            )
        )
        or 0
    )
    if ready_sources == 0:
        raise AppError(
            "Course has no ready sources to build knowledge base from",
            code="no_content",
            status_code=409,
        )

    course.kb_status = "building"
    course.kb_error = None
    db.commit()

    background_tasks.add_task(kb_svc.build_sync, course_id)

    return KBRebuildResponse(kb_status="building")


@router.get("/courses/{course_id}/topics", response_model=List[TopicTreeNode])
def get_course_topics(
    course_id: int,
    db: Session = Depends(get_db),
) -> List[TopicTreeNode]:
    """Get the hierarchical topic tree for a course."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    topics = list(
        db.scalars(
            select(Topic)
            .where(Topic.course_id == course_id)
            .order_by(Topic.order_index.asc(), Topic.id.asc())
        ).all()
    )

    # Pre-fetch chunk counts and concept counts for leaf topics
    chunk_counts_by_topic: Dict[int, Set[int]] = {}
    chunk_topics = db.execute(
        select(ChunkTopic.topic_id, ChunkTopic.chunk_id).join(
            Topic, Topic.id == ChunkTopic.topic_id
        ).where(Topic.course_id == course_id)
    ).all()
    for tid, cid in chunk_topics:
        chunk_counts_by_topic.setdefault(tid, set()).add(cid)

    concept_counts_by_topic: Dict[int, int] = {}
    concept_rows = db.execute(
        select(Concept.topic_id, func.count(Concept.id))
        .where(Concept.course_id == course_id)
        .group_by(Concept.topic_id)
    ).all()
    for tid, cnt in concept_rows:
        concept_counts_by_topic[tid] = cnt

    # Build hierarchy map
    children_by_parent: Dict[Optional[int], List[Topic]] = {}
    for t in topics:
        children_by_parent.setdefault(t.parent_id, []).append(t)

    def build_node(topic: Topic) -> TopicTreeNode:
        child_topics = children_by_parent.get(topic.id, [])
        is_leaf = len(child_topics) == 0

        child_nodes: List[TopicTreeNode] = []
        distinct_chunks: Set[int] = set(chunk_counts_by_topic.get(topic.id, set()))

        for child in child_topics:
            child_node = build_node(child)
            child_nodes.append(child_node)
            distinct_chunks.update(chunk_counts_by_topic.get(child.id, set()))

        # For parent topics, chunk_count is distinct chunks across children
        chunk_count = len(distinct_chunks)
        concept_count = concept_counts_by_topic.get(topic.id, 0)

        return TopicTreeNode(
            id=topic.id,
            name=topic.name,
            description=topic.description,
            order_index=topic.order_index,
            parent_id=topic.parent_id,
            is_leaf=is_leaf,
            chunk_count=chunk_count,
            concept_count=concept_count,
            children=child_nodes,
        )

    root_topics = children_by_parent.get(None, [])
    return [build_node(root) for root in root_topics]


@router.get("/courses/{course_id}/concepts", response_model=List[ConceptItem])
def get_course_concepts(
    course_id: int,
    topic_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> List[ConceptItem]:
    """Get all key concepts for a course, optionally filtered by topic."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    stmt = (
        select(Concept, Topic.name)
        .join(Topic, Topic.id == Concept.topic_id)
        .where(Concept.course_id == course_id)
    )
    if topic_id is not None:
        stmt = stmt.where(Concept.topic_id == topic_id)

    stmt = stmt.order_by(Topic.order_index.asc(), Concept.name.asc())
    results = db.execute(stmt).all()

    return [
        ConceptItem(
            id=c.id,
            name=c.name,
            definition=c.definition,
            topic_id=c.topic_id,
            topic_name=topic_name,
        )
        for c, topic_name in results
    ]


@router.get("/topics/{topic_id}", response_model=TopicDetailResponse)
def get_topic_detail(
    topic_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> TopicDetailResponse:
    """Get detailed topic information with relationships, concepts, and citations."""
    topic = db.get(Topic, topic_id)
    if not topic:
        raise AppError(
            f"Topic with id {topic_id} not found",
            code="topic_not_found",
            status_code=404,
        )

    parent_brief = (
        TopicBrief(id=topic.parent.id, name=topic.parent.name)
        if topic.parent
        else None
    )

    children_brief = [
        TopicBrief(id=c.id, name=c.name)
        for c in sorted(topic.subtopics, key=lambda x: (x.order_index, x.id))
    ]

    concepts_brief = [
        ConceptBrief(id=c.id, name=c.name, definition=c.definition)
        for c in sorted(topic.concepts, key=lambda x: x.name)
    ]

    # Prerequisites of this topic (from TopicPrereq where topic_id == topic_id)
    prereq_rows = db.execute(
        select(Topic.id, Topic.name)
        .join(TopicPrereq, TopicPrereq.prereq_topic_id == Topic.id)
        .where(TopicPrereq.topic_id == topic.id)
        .order_by(Topic.order_index.asc(), Topic.name.asc())
    ).all()
    prerequisites = [TopicBrief(id=row[0], name=row[1]) for row in prereq_rows]

    # Unlocks: topics that list this topic as a prerequisite
    unlock_rows = db.execute(
        select(Topic.id, Topic.name)
        .join(TopicPrereq, TopicPrereq.topic_id == Topic.id)
        .where(TopicPrereq.prereq_topic_id == topic.id)
        .order_by(Topic.order_index.asc(), Topic.name.asc())
    ).all()
    unlocks = [TopicBrief(id=row[0], name=row[1]) for row in unlock_rows]

    # Chunks associated with this topic (or its children if parent topic)
    is_parent = len(topic.subtopics) > 0
    if is_parent:
        child_ids = [c.id for c in topic.subtopics]
        # Query distinct chunks across children, with max relevance
        subq = (
            select(
                ChunkTopic.chunk_id,
                func.max(ChunkTopic.relevance).label("max_relevance"),
            )
            .where(ChunkTopic.topic_id.in_(child_ids))
            .group_by(ChunkTopic.chunk_id)
            .subquery()
        )

        total_chunks = (
            db.scalar(select(func.count(subq.c.chunk_id))) or 0
        )

        chunk_rows = db.execute(
            select(Chunk, Source, subq.c.max_relevance)
            .join(subq, Chunk.id == subq.c.chunk_id)
            .join(Source, Source.id == Chunk.source_id)
            .order_by(subq.c.max_relevance.desc(), Chunk.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    else:
        # Leaf topic: direct ChunkTopic associations
        total_chunks = (
            db.scalar(
                select(func.count(ChunkTopic.chunk_id)).where(
                    ChunkTopic.topic_id == topic.id
                )
            )
            or 0
        )

        chunk_rows = db.execute(
            select(Chunk, Source, ChunkTopic.relevance)
            .join(ChunkTopic, Chunk.id == ChunkTopic.chunk_id)
            .join(Source, Source.id == Chunk.source_id)
            .where(ChunkTopic.topic_id == topic.id)
            .order_by(ChunkTopic.relevance.desc(), Chunk.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()

    citations: List[Citation] = [
        build_citation(chunk, source, score=float(rel))
        for chunk, source, rel in chunk_rows
    ]

    return TopicDetailResponse(
        id=topic.id,
        name=topic.name,
        description=topic.description,
        parent=parent_brief,
        children=children_brief,
        concepts=concepts_brief,
        prerequisites=prerequisites,
        unlocks=unlocks,
        chunk_count=total_chunks,
        chunks=citations,
    )


@router.get("/courses/{course_id}/graph", response_model=GraphResponse)
def get_course_knowledge_graph(
    course_id: int,
    db: Session = Depends(get_db),
) -> GraphResponse:
    """Get the topic relationship graph containing all topics and prerequisite edges."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    topics = list(
        db.scalars(
            select(Topic)
            .where(Topic.course_id == course_id)
            .order_by(Topic.order_index.asc(), Topic.id.asc())
        ).all()
    )

    # Compute chunk counts for all topics
    chunk_counts_by_topic: Dict[int, Set[int]] = {}
    chunk_topics = db.execute(
        select(ChunkTopic.topic_id, ChunkTopic.chunk_id).join(
            Topic, Topic.id == ChunkTopic.topic_id
        ).where(Topic.course_id == course_id)
    ).all()
    for tid, cid in chunk_topics:
        chunk_counts_by_topic.setdefault(tid, set()).add(cid)

    # Hierarchy map
    children_by_parent: Dict[Optional[int], List[Topic]] = {}
    for t in topics:
        children_by_parent.setdefault(t.parent_id, []).append(t)

    nodes: List[GraphNode] = []
    for t in topics:
        children = children_by_parent.get(t.id, [])
        is_leaf = len(children) == 0
        level = 0 if t.parent_id is None else 1

        if is_leaf:
            chunk_count = len(chunk_counts_by_topic.get(t.id, set()))
        else:
            # Union of chunks across descendants
            descendant_chunks: Set[int] = set()
            for child in children:
                descendant_chunks.update(chunk_counts_by_topic.get(child.id, set()))
            chunk_count = len(descendant_chunks)

        nodes.append(
            GraphNode(
                id=t.id,
                name=t.name,
                parent_id=t.parent_id,
                level=level,
                is_leaf=is_leaf,
                chunk_count=chunk_count,
            )
        )

    # Prerequisite edges: from -> to where 'from' is prerequisite of 'to'
    prereq_edges = db.execute(
        select(TopicPrereq.prereq_topic_id, TopicPrereq.topic_id).where(
            TopicPrereq.course_id == course_id
        )
    ).all()

    edges: List[GraphEdge] = [
        GraphEdge(from_=row[0], to=row[1]) for row in prereq_edges
    ]

    return GraphResponse(nodes=nodes, edges=edges)
