from functools import lru_cache
import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class KBService:
    """Manages course-level knowledge base build execution, concurrency locks, and progress."""

    def __init__(self) -> None:
        self._locks: Dict[int, threading.Lock] = {}
        self._pending: Dict[int, bool] = {}
        self._progress: Dict[int, Dict[str, Any]] = {}
        self._global_lock = threading.Lock()
        self.build_count: Dict[int, int] = {}
        self._build_delay: float = 0.0

    def _get_course_lock(self, course_id: int) -> threading.Lock:
        with self._global_lock:
            if course_id not in self._locks:
                self._locks[course_id] = threading.Lock()
            return self._locks[course_id]

    def is_building(self, course_id: int) -> bool:
        """Check whether a build is actively running for the course."""
        lock = self._get_course_lock(course_id)
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
            return False
        return True

    def get_progress(self, course_id: int) -> Dict[str, Any]:
        """Get in-memory stage and progress for a course build."""
        return self._progress.get(course_id, {"stage": "idle", "progress": 0})

    def request_build(self, course_id: int) -> bool:
        """Trigger an asynchronous knowledge base build.

        If a build is currently executing, flags pending=True to trigger exactly one subsequent rebuild.
        """
        lock = self._get_course_lock(course_id)
        if not lock.acquire(blocking=False):
            with self._global_lock:
                self._pending[course_id] = True
            logger.info("KB build in progress for course %d; flagged pending.", course_id)
            return False

        with self._global_lock:
            self._pending[course_id] = False

        def _worker() -> None:
            try:
                while True:
                    def _progress_cb(stage: str, prog: int) -> None:
                        self._progress[course_id] = {"stage": stage, "progress": prog}

                    if self._build_delay > 0:
                        import time
                        time.sleep(self._build_delay)

                    from app.services.kb.builder import build_knowledge_base

                    build_knowledge_base(course_id, progress_callback=_progress_cb)

                    with self._global_lock:
                        self.build_count[course_id] = self.build_count.get(course_id, 0) + 1
                        if self._pending.get(course_id, False):
                            self._pending[course_id] = False
                        else:
                            break
            finally:
                lock.release()

        worker_thread = threading.Thread(
            target=_worker,
            name=f"kb-worker-{course_id}",
            daemon=True,
        )
        worker_thread.start()
        return True

    def build_sync(self, course_id: int) -> None:
        """Run knowledge base build synchronously under the course lock."""
        lock = self._get_course_lock(course_id)
        with lock:
            with self._global_lock:
                self._pending[course_id] = False
            while True:
                def _progress_cb(stage: str, prog: int) -> None:
                    self._progress[course_id] = {"stage": stage, "progress": prog}

                if self._build_delay > 0:
                    import time
                    time.sleep(self._build_delay)

                from app.services.kb.builder import build_knowledge_base

                build_knowledge_base(course_id, progress_callback=_progress_cb)

                with self._global_lock:
                    self.build_count[course_id] = self.build_count.get(course_id, 0) + 1
                    if self._pending.get(course_id, False):
                        self._pending[course_id] = False
                    else:
                        break


@lru_cache
def get_kb_service() -> KBService:
    """Singleton getter for KBService."""
    return KBService()
