from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_db
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.student import Student
from app.schemas.tutor import (
    ConversationCreate,
    ConversationDeleteResponse,
    ConversationListItem,
    ConversationRead,
    MessageCreate,
    MessageRead,
    RelatedTopicItem,
    TutorResponse,
)
from app.services.auth.dependencies import (
    get_current_student,
    resolve_student_id,
)
from app.services.tutor.service import get_tutor_service

router = APIRouter(tags=["tutor"])


@router.post(
    "/courses/{course_id}/conversations",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    course_id: int,
    payload: ConversationCreate,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> ConversationRead:
    """Create a new chat conversation session for a course."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    resolved_sid = resolve_student_id(current_student, payload.student_id)
    student = db.get(Student, resolved_sid)
    if not student:
        raise AppError(
            f"Student with id {resolved_sid} not found",
            code="student_not_found",
            status_code=404,
        )

    title = payload.title.strip() if payload.title and payload.title.strip() else "New Conversation"

    conversation = Conversation(
        course_id=course_id,
        student_id=resolved_sid,
        title=title,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return ConversationRead(
        id=conversation.id,
        course_id=conversation.course_id,
        student_id=conversation.student_id,
        title=conversation.title,
        created_at=conversation.created_at,
        message_count=0,
    )


@router.get(
    "/courses/{course_id}/conversations",
    response_model=List[ConversationListItem],
)
def list_course_conversations(
    course_id: int,
    student_id: Optional[int] = Query(default=None, description="Student ID to filter conversations"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> List[ConversationListItem]:
    """List conversations for a course and student, ordered newest first."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    resolved_sid = resolve_student_id(current_student, student_id)
    student = db.get(Student, resolved_sid)
    if not student:
        raise AppError(
            f"Student with id {resolved_sid} not found",
            code="student_not_found",
            status_code=404,
        )

    convs = list(
        db.scalars(
            select(Conversation)
            .where(
                Conversation.course_id == course_id,
                Conversation.student_id == resolved_sid,
            )
            .order_by(Conversation.created_at.desc(), Conversation.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    items: List[ConversationListItem] = []
    for c in convs:
        msg_count = (
            db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == c.id)
            )
            or 0
        )
        last_msg = db.scalar(
            select(Message)
            .where(Message.conversation_id == c.id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        last_preview = last_msg.content[:80] if last_msg else None

        items.append(
            ConversationListItem(
                id=c.id,
                course_id=c.course_id,
                student_id=c.student_id,
                title=c.title,
                created_at=c.created_at,
                message_count=msg_count,
                last_message_preview=last_preview,
            )
        )

    return items


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationRead,
)
def get_conversation(
    conversation_id: int,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> ConversationRead:
    """Retrieve conversation details and message count."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise AppError(
            f"Conversation with id {conversation_id} not found",
            code="conversation_not_found",
            status_code=404,
        )

    settings = get_settings()
    if settings.auth_required and current_student:
        if conv.student_id != current_student.id:
            raise AppError(
                f"Conversation with id {conversation_id} not found",
                code="conversation_not_found",
                status_code=404,
            )

    msg_count = (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.conversation_id == conversation_id
            )
        )
        or 0
    )

    return ConversationRead(
        id=conv.id,
        course_id=conv.course_id,
        student_id=conv.student_id,
        title=conv.title,
        created_at=conv.created_at,
        message_count=msg_count,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=List[MessageRead],
)
def get_conversation_messages(
    conversation_id: int,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> List[MessageRead]:
    """Retrieve message history for a conversation, ordered oldest first."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise AppError(
            f"Conversation with id {conversation_id} not found",
            code="conversation_not_found",
            status_code=404,
        )

    settings = get_settings()
    if settings.auth_required and current_student:
        if conv.student_id != current_student.id:
            raise AppError(
                f"Conversation with id {conversation_id} not found",
                code="conversation_not_found",
                status_code=404,
            )

    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
    )

    output: List[MessageRead] = []
    for m in messages:
        meta = m.meta or {}
        related_topics_raw = meta.get("related_topics", [])
        related_topics = [
            RelatedTopicItem(id=t["id"], name=t["name"])
            for t in related_topics_raw
            if isinstance(t, dict) and "id" in t and "name" in t
        ]

        output.append(
            MessageRead(
                id=m.id,
                role=m.role,
                content=m.content,
                grounding=m.grounding_status,
                citations=m.citations or [],
                outside_knowledge_note=meta.get("outside_knowledge_note"),
                followups=meta.get("followups", []),
                related_topics=related_topics,
                mastery_nudge=meta.get("mastery_nudge"),
                created_at=m.created_at,
            )
        )

    return output


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=TutorResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_conversation_message(
    conversation_id: int,
    payload: MessageCreate,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> TutorResponse:
    """Send a student question to the AI tutor and receive a source-grounded response."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise AppError(
            f"Conversation with id {conversation_id} not found",
            code="conversation_not_found",
            status_code=404,
        )

    settings = get_settings()
    if settings.auth_required and current_student:
        if conv.student_id != current_student.id:
            raise AppError(
                f"Conversation with id {conversation_id} not found",
                code="conversation_not_found",
                status_code=404,
            )

    resolved_sid = resolve_student_id(current_student, payload.student_id)
    if conv.student_id != resolved_sid:
        raise AppError(
            "Student does not have access to this conversation",
            code="forbidden_student",
            status_code=403,
        )

    tutor = get_tutor_service()
    return tutor.answer(
        db=db,
        conversation=conv,
        student_id=resolved_sid,
        content=payload.content,
        topic_ids=payload.topic_ids,
    )


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ConversationDeleteResponse,
)
def delete_conversation(
    conversation_id: int,
    current_student: Optional[Student] = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> ConversationDeleteResponse:
    """Delete conversation and all its messages (cascade)."""
    conv = db.get(Conversation, conversation_id)
    if not conv:
        raise AppError(
            f"Conversation with id {conversation_id} not found",
            code="conversation_not_found",
            status_code=404,
        )

    settings = get_settings()
    if settings.auth_required and current_student:
        if conv.student_id != current_student.id:
            raise AppError(
                f"Conversation with id {conversation_id} not found",
                code="conversation_not_found",
                status_code=404,
            )

    db.delete(conv)
    db.commit()

    return ConversationDeleteResponse(deleted=True)
