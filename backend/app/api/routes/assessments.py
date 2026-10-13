"""Assessment creation, retrieval, listing, and deletion endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.session import get_db
from app.models.assessment import Assessment, Attempt, Question
from app.models.course import Course
from app.models.student import Student
from app.schemas.assessment import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    AssessmentCreate,
    AssessmentDeleteResponse,
    AssessmentListItem,
    AssessmentOut,
    AssessmentReportResponse,
)
from app.services.assessment.answering import AnswerService
from app.services.assessment.reporting import build_report, submit_assessment
from app.services.assessment.service import get_assessment_service
from app.services.vector_store import get_vector_store

router = APIRouter(tags=["assessments"])


@router.post(
    "/courses/{course_id}/assessments",
    response_model=AssessmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_assessment(
    course_id: int,
    payload: AssessmentCreate,
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Create a new source-grounded assessment (quiz, mock exam, or diagnostic)."""
    svc = get_assessment_service()
    return svc.create(
        db=db,
        course_id=course_id,
        student_id=payload.student_id,
        kind=payload.kind,
        topic_ids=payload.topic_ids,
        num_questions=payload.num_questions,
        difficulty=payload.difficulty,
        question_types=payload.question_types,
        title=payload.title,
    )


@router.post(
    "/courses/{course_id}/diagnostic",
    response_model=AssessmentOut,
)
def create_or_resume_diagnostic(
    course_id: int,
    response: Response,
    student_id: int = Query(..., description="Student ID taking the diagnostic"),
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Create a diagnostic assessment or resume an existing in-progress diagnostic."""
    # Check if student already has an in-progress diagnostic for this course
    existing_in_progress = db.scalar(
        select(Assessment)
        .where(
            Assessment.course_id == course_id,
            Assessment.student_id == student_id,
            Assessment.kind == "diagnostic",
            Assessment.status == "in_progress",
        )
        .order_by(Assessment.created_at.desc())
        .limit(1)
    )

    if existing_in_progress:
        # Return 200 OK and existing diagnostic
        if response:
            response.status_code = status.HTTP_200_OK
        svc = get_assessment_service()
        questions = list(
            db.scalars(
                select(Question)
                .where(Question.assessment_id == existing_in_progress.id)
                .order_by(Question.position.asc(), Question.id.asc())
            ).all()
        )
        return svc._format_assessment_out(
            db=db,
            assessment=existing_in_progress,
            question_rows=questions,
            warnings=[],
            generation_report=existing_in_progress.config.get("generation_report", {}),
        )

    # Otherwise create a new diagnostic assessment with 201 Created
    if response:
        response.status_code = status.HTTP_201_CREATED

    svc = get_assessment_service()
    return svc.create(
        db=db,
        course_id=course_id,
        student_id=student_id,
        kind="diagnostic",
        topic_ids=None,
        num_questions=None,
        difficulty="auto",
        question_types=["mcq"],
        title="Diagnostic Assessment",
    )


@router.get(
    "/assessments/{assessment_id}",
    response_model=AssessmentOut,
)
def get_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
) -> AssessmentOut:
    """Retrieve assessment details and questions."""
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise AppError(
            f"Assessment with id {assessment_id} not found",
            code="assessment_not_found",
            status_code=404,
        )

    questions = list(
        db.scalars(
            select(Question)
            .where(Question.assessment_id == assessment_id)
            .order_by(Question.position.asc(), Question.id.asc())
        ).all()
    )

    # Check answered status per question
    attempt_question_ids = set(
        db.scalars(
            select(Attempt.question_id).where(Attempt.assessment_id == assessment_id)
        ).all()
    )

    svc = get_assessment_service()
    return svc._format_assessment_out(
        db=db,
        assessment=assessment,
        question_rows=questions,
        warnings=[],
        generation_report=assessment.config.get("generation_report", {}),
    )


@router.post(
    "/assessments/{assessment_id}/questions/{question_id}/answer",
    response_model=AnswerSubmitResponse,
    status_code=status.HTTP_200_OK,
)
def submit_question_answer(
    assessment_id: int,
    question_id: int,
    payload: AnswerSubmitRequest,
    db: Session = Depends(get_db),
) -> AnswerSubmitResponse:
    """Submit and grade an answer for a single assessment question."""
    return AnswerService.submit_answer(
        db=db,
        assessment_id=assessment_id,
        question_id=question_id,
        answer=payload.answer,
        time_taken_sec=payload.time_taken_sec,
        student_id=payload.student_id,
    )


@router.post(
    "/assessments/{assessment_id}/submit",
    response_model=AssessmentReportResponse,
    status_code=status.HTTP_200_OK,
)
def submit_assessment_route(
    assessment_id: int,
    db: Session = Depends(get_db),
) -> AssessmentReportResponse:
    """Submit an in-progress assessment and receive full performance report."""
    return submit_assessment(db=db, assessment_id=assessment_id)


@router.get(
    "/assessments/{assessment_id}/report",
    response_model=AssessmentReportResponse,
    status_code=status.HTTP_200_OK,
)
def get_assessment_report(
    assessment_id: int,
    db: Session = Depends(get_db),
) -> AssessmentReportResponse:
    """Retrieve full performance report for a submitted assessment."""
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise AppError(
            f"Assessment with id {assessment_id} not found",
            code="assessment_not_found",
            status_code=404,
        )
    return build_report(db=db, assessment=assessment)


@router.get(
    "/courses/{course_id}/assessments",
    response_model=List[AssessmentListItem],
)
def list_course_assessments(
    course_id: int,
    student_id: int = Query(..., description="Student ID"),
    db: Session = Depends(get_db),
) -> List[AssessmentListItem]:
    """List assessments for a course and student, ordered newest first."""
    course = db.get(Course, course_id)
    if not course:
        raise AppError(
            f"Course with id {course_id} not found",
            code="course_not_found",
            status_code=404,
        )

    student = db.get(Student, student_id)
    if not student:
        raise AppError(
            f"Student with id {student_id} not found",
            code="student_not_found",
            status_code=404,
        )

    assessments = list(
        db.scalars(
            select(Assessment)
            .where(
                Assessment.course_id == course_id,
                Assessment.student_id == student_id,
            )
            .order_by(Assessment.created_at.desc(), Assessment.id.desc())
        ).all()
    )

    items: List[AssessmentListItem] = []
    for a in assessments:
        q_count = (
            db.scalar(
                select(func.count(Question.id)).where(Question.assessment_id == a.id)
            )
            or 0
        )
        answered_count = (
            db.scalar(
                select(func.count(func.distinct(Attempt.question_id))).where(
                    Attempt.assessment_id == a.id
                )
            )
            or 0
        )

        items.append(
            AssessmentListItem(
                id=a.id,
                kind=a.kind,
                status=a.status,
                title=a.title,
                num_questions=q_count,
                answered_count=answered_count,
                score=a.score,
                created_at=a.created_at,
                submitted_at=a.submitted_at,
            )
        )

    return items


@router.delete(
    "/assessments/{assessment_id}",
    response_model=AssessmentDeleteResponse,
)
def delete_assessment(
    assessment_id: int,
    db: Session = Depends(get_db),
) -> AssessmentDeleteResponse:
    """Delete an assessment and its questions and question vectors."""
    assessment = db.get(Assessment, assessment_id)
    if not assessment:
        raise AppError(
            f"Assessment with id {assessment_id} not found",
            code="assessment_not_found",
            status_code=404,
        )

    # Delete from DB (cascade removes questions and attempts)
    db.delete(assessment)
    db.commit()

    # Delete vectors from VectorStore
    vstore = get_vector_store()
    try:
        vstore.delete_questions_by_assessment(assessment_id)
    except Exception as exc:
        logger.warning(
            "Could not delete vectors for assessment %d: %s", assessment_id, exc
        )

    return AssessmentDeleteResponse(deleted=True)
