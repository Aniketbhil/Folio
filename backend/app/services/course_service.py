import logging
import shutil
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import AppError
from app.models.course import Course
from app.services.vector_store import get_vector_store

logger = logging.getLogger(__name__)


def delete_course(db: Session, course_id: int) -> bool:
    """Delete a course and all associated resources:

    1. Removes course upload folder on disk.
    2. Removes chunks and questions from Chroma vector collections.
    3. Deletes Course database entity which cascades to all children.
    """
    settings = get_settings()
    vector_store = get_vector_store()

    course = db.get(Course, course_id)
    if not course:
        raise AppError(message="Course not found", code="not_found", status_code=404)

    # 1. Remove uploaded files directory if present
    course_dir = Path(settings.upload_dir) / str(course_id)
    if course_dir.exists():
        try:
            shutil.rmtree(course_dir)
            logger.info("Deleted course upload directory: %s", course_dir)
        except Exception as exc:
            logger.warning(
                "Failed to delete upload folder for course %d: %s", course_id, exc
            )

    # 2. Remove vector entries from both Chroma collections
    try:
        vector_store.delete_by_course(course_id)
        vector_store.delete_questions_by_course(course_id)
        logger.info("Deleted vector embeddings for course %d", course_id)
    except Exception as exc:
        logger.warning(
            "Failed to delete vector entries for course %d: %s", course_id, exc
        )

    # 3. Delete database row (cascades to all children)
    db.delete(course)
    db.commit()
    logger.info("Successfully deleted course %d from database", course_id)

    return True
