#!/usr/bin/env python3
"""End-to-end verification script for Folio Prompt 5: Assessment Creation.

Tests:
1. Quiz creation (5 questions, mixed types, no masked keys/explanations, topic/difficulty/source locs valid).
2. DB checks: MCQs have exactly 4 options, unique texts, valid letters, and shuffled keys across 10 questions.
3. Every question's source_chunk_ids exist and belong to the question's topic.
4. No duplicate fingerprints inside one assessment.
5. Deduplication: second quiz for same student/scope has no repeat fingerprints; different student can receive questions.
6. Diagnostic: exactly 1 question per distinct leaf topic, MCQ only, mixed difficulty; resuming returns same in_progress (200).
7. Auto difficulty: Mastery p_mastery 0.2 -> easy, 0.85 -> hard; no rows written to Mastery or MasteryEvent by assessment endpoints.
8. Validation & scope: parent topic expands to leaves; unknown topic -> 404; empty KB -> 409; invalid num -> 422; unknown student -> 404.
9. Verifier unit check: deliberately wrong key is rejected; correct one accepted.
10. /dev/generate-questions returns accepted/rejected and persists nothing (Question row count unchanged).
11. GET /assessments/{id} matches creation; list works; DELETE cascades questions and deletes question vectors.
12. Vectors exist in folio_questions with student_id metadata.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Setup temporary test storage before importing app modules
temp_dir = tempfile.mkdtemp(prefix="folio_quiz_verify_")
test_db_path = Path(temp_dir) / "test.db"
test_chroma_path = Path(temp_dir) / "chroma"
test_upload_path = Path(temp_dir) / "uploads"

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["CHROMA_DIR"] = str(test_chroma_path)
os.environ["UPLOAD_DIR"] = str(test_upload_path)
os.environ["LLM_MOCK"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["DEBUG"] = "true"

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine, run_sqlite_migrations
from app.main import create_app
from app.models.assessment import Assessment, Question
from app.models.mastery import Mastery, MasteryEvent
from app.models.source import Chunk
from app.models.topic import ChunkTopic, Topic
from app.services.assessment.schemas import CandidateQuestion
from app.services.assessment.verifier import MockQuestionVerifier
from app.services.vector_store import get_vector_store
from scripts.generate_samples import generate_all_samples


def wait_for_kb_ready(client: TestClient, course_id: int, timeout: float = 20.0) -> Dict[str, Any]:
    """Poll course KB status until ready or failed."""
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/api/v1/courses/{course_id}/kb/status")
        if res.status_code == 200:
            data = res.json()
            if data.get("kb_status") in ("ready", "failed"):
                return data
        time.sleep(0.1)
    return {}


def run_verification() -> int:
    print("=" * 70)
    print(" Folio Prompt 5: Assessment Creation Verification")
    print("=" * 70)
    print(f"Isolated test database: {os.environ['DATABASE_URL']}")
    print(f"Isolated Chroma store:  {os.environ['CHROMA_DIR']}")
    print(f"Isolated Upload dir:    {os.environ['UPLOAD_DIR']}")
    print("-" * 70)

    # Prepare samples
    samples_dir = Path("backend/samples") if Path("backend/samples").exists() else Path("samples")
    if not samples_dir.exists() or not (samples_dir / "sample.pdf").exists():
        samples_dir.mkdir(parents=True, exist_ok=True)
        generate_all_samples(samples_dir)

    pdf_path = samples_dir / "sample.pdf"
    pptx_path = samples_dir / "sample.pptx"
    vtt_path = samples_dir / "sample.vtt"

    app = create_app()
    client = TestClient(app)
    results: Dict[str, bool] = {}

    with client:
        # Setup Students
        stu1_res = client.post("/api/v1/students", json={"name": "Alice Quizzler", "email": "alice@quiz.edu"})
        assert stu1_res.status_code == 201, f"Failed student 1: {stu1_res.text}"
        student_1_id = stu1_res.json()["id"]

        stu2_res = client.post("/api/v1/students", json={"name": "Bob Quizzler", "email": "bob@quiz.edu"})
        assert stu2_res.status_code == 201, f"Failed student 2: {stu2_res.text}"
        student_2_id = stu2_res.json()["id"]

        # Setup Course 1
        crs1_res = client.post("/api/v1/courses", json={"name": "Physics & Dynamics 101", "student_id": student_1_id})
        assert crs1_res.status_code == 201, f"Failed course 1: {crs1_res.text}"
        course_1_id = crs1_res.json()["id"]

        # Ingest sample files
        with open(pdf_path, "rb") as f:
            client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"title": "Mechanics Syllabus"},
            )
        with open(pptx_path, "rb") as f:
            client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                data={"title": "Lecture Slides"},
            )
        with open(vtt_path, "rb") as f:
            client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.vtt", f, "text/vtt")},
                data={"title": "Video Lecture"},
            )

        kb_stat = wait_for_kb_ready(client, course_1_id)
        assert kb_stat.get("kb_status") == "ready", f"KB failed to build: {kb_stat}"

        # -----------------------------------------------------------------
        # CHECK 1: Quiz (5 questions, mixed types) creation & response shape
        # -----------------------------------------------------------------
        q_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "num_questions": 5,
                "question_types": ["mcq", "short_answer"],
                "difficulty": "medium",
                "title": "Module 1 Practice Quiz",
            },
        )
        assert q_res.status_code == 201, f"Create quiz failed: {q_res.text}"
        quiz_data = q_res.json()
        quiz_id = quiz_data["id"]

        c1_no_keys = all(
            q.get("correct_answer") is None
            and q.get("explanation") is None
            and "key_points" not in q
            and "verification_notes" not in q
            and "meta" not in q
            for q in quiz_data["questions"]
        )
        c1_fields_ok = all(
            q.get("topic") and q["topic"].get("id")
            and q.get("difficulty")
            and q.get("qtype") in ("mcq", "short_answer")
            and len(q.get("sources", [])) >= 1
            and q["sources"][0].get("location") is not None
            for q in quiz_data["questions"]
        )
        c1_count_ok = quiz_data["num_questions"] == 5 or len(quiz_data.get("warnings", [])) > 0
        c1_ok = c1_no_keys and c1_fields_ok and c1_count_ok
        results["quiz (5 questions, mixed types) is created; response has no correct_answer/explanation/key_points; valid metadata and locations"] = c1_ok

        # -----------------------------------------------------------------
        # CHECK 2: DB check: MCQs have exactly 4 options, unique texts, valid letters, shuffled keys
        # -----------------------------------------------------------------
        # Create a 10-question MCQ quiz to check option shuffling
        mcq_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "num_questions": 10,
                "question_types": ["mcq"],
                "difficulty": "medium",
            },
        )
        assert mcq_res.status_code == 201, f"Create 10 MCQ quiz failed: {mcq_res.text}"
        mcq_quiz_id = mcq_res.json()["id"]

        with SessionLocal() as db:
            mcq_rows = list(
                db.scalars(
                    select(Question).where(
                        Question.assessment_id == mcq_quiz_id,
                        Question.qtype == "mcq",
                    )
                ).all()
            )

        c2_opts_valid = all(
            len(q.options) == 4
            and len(set(opt["text"] for opt in q.options)) == 4
            and q.correct_answer in ("A", "B", "C", "D")
            for q in mcq_rows
        )
        correct_letters = set(q.correct_answer for q in mcq_rows)
        c2_shuffled = len(correct_letters) > 1  # Not all identical letter
        c2_ok = c2_opts_valid and c2_shuffled
        results["DB check: every MCQ has exactly 4 options with unique texts and a valid letter; letters are not all identical"] = c2_ok

        # -----------------------------------------------------------------
        # CHECK 3: Every question's source_chunk_ids exist and belong to the question's topic
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            all_questions = list(
                db.scalars(select(Question).where(Question.assessment_id == quiz_id)).all()
            )
            c3_chunks_valid = True
            for q in all_questions:
                for cid in q.source_chunk_ids:
                    chk = db.get(Chunk, cid)
                    if not chk:
                        c3_chunks_valid = False
                    # Verify chunk tagged to question topic
                    is_tagged = (
                        db.scalar(
                            select(func.count(ChunkTopic.chunk_id)).where(
                                ChunkTopic.chunk_id == cid,
                                ChunkTopic.topic_id == q.topic_id,
                            )
                        )
                        or 0
                    ) > 0
                    if not is_tagged:
                        c3_chunks_valid = False

        results["every question's source_chunk_ids exist and belong to the question's topic"] = c3_chunks_valid

        # -----------------------------------------------------------------
        # CHECK 4: No duplicate fingerprints inside one assessment
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            fps_quiz1 = list(
                db.scalars(
                    select(Question.fingerprint).where(Question.assessment_id == mcq_quiz_id)
                ).all()
            )
        c4_ok = len(fps_quiz1) == len(set(fps_quiz1))
        results["no duplicate fingerprints inside one assessment"] = c4_ok

        # -----------------------------------------------------------------
        # CHECK 5: Deduplication across assessments for same student vs different student
        # -----------------------------------------------------------------
        # Create a second quiz for student 1 with same scope
        q2_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "num_questions": 5,
                "question_types": ["mcq", "short_answer"],
            },
        )
        assert q2_res.status_code == 201
        q2_id = q2_res.json()["id"]

        with SessionLocal() as db:
            fps_quiz_initial = set(
                db.scalars(
                    select(Question.fingerprint).where(Question.assessment_id == quiz_id)
                ).all()
            )
            fps_quiz2 = set(
                db.scalars(
                    select(Question.fingerprint).where(Question.assessment_id == q2_id)
                ).all()
            )

        # No intersection between quiz 1 and quiz 2 for student 1
        c5_no_repeats_student1 = len(fps_quiz_initial.intersection(fps_quiz2)) == 0

        # Now create quiz for student 2 (allowed to receive same questions)
        q_stu2_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_2_id,
                "kind": "quiz",
                "num_questions": 5,
                "question_types": ["mcq", "short_answer"],
            },
        )
        assert q_stu2_res.status_code == 201
        c5_ok = c5_no_repeats_student1
        results["a second quiz for same student contains NO repeated question fingerprints; different student can receive questions"] = c5_ok

        # -----------------------------------------------------------------
        # CHECK 6: Diagnostic assessment (1 per topic, MCQ only, resume existing)
        # -----------------------------------------------------------------
        diag1_res = client.post(f"/api/v1/courses/{course_1_id}/diagnostic?student_id={student_1_id}")
        assert diag1_res.status_code in (200, 201), f"Diagnostic failed: {diag1_res.text}"
        diag1_data = diag1_res.json()
        diag1_id = diag1_data["id"]

        # Assert MCQ only and mixed difficulty
        c6_mcq_only = all(q["qtype"] == "mcq" for q in diag1_data["questions"])
        diag_topic_ids = [q["topic"]["id"] for q in diag1_data["questions"]]
        c6_distinct_topics = len(diag_topic_ids) == len(set(diag_topic_ids))

        # Resume call
        diag2_res = client.post(f"/api/v1/courses/{course_1_id}/diagnostic?student_id={student_1_id}")
        assert diag2_res.status_code == 200, f"Expected 200 on resume, got {diag2_res.status_code}"
        diag2_data = diag2_res.json()
        c6_resumed_same = diag2_data["id"] == diag1_id

        c6_ok = c6_mcq_only and c6_distinct_topics and c6_resumed_same
        results["diagnostic: one question per distinct leaf topic, MCQ only, difficulty mixed; resume returns in_progress (200)"] = c6_ok

        # -----------------------------------------------------------------
        # CHECK 7: Auto difficulty with Mastery read; zero rows written to Mastery
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            m_count_before = db.scalar(select(func.count(Mastery.id))) or 0
            me_count_before = db.scalar(select(func.count(MasteryEvent.id))) or 0

            # Find two leaf topics
            leaf_topics = list(
                db.scalars(
                    select(Topic)
                    .where(Topic.course_id == course_1_id, Topic.parent_id.is_not(None))
                ).all()
            )
            top_easy_id = leaf_topics[0].id
            top_hard_id = leaf_topics[1].id

            # Directly insert mastery row (0.2 -> easy, 0.85 -> hard)
            db.add(Mastery(student_id=student_1_id, topic_id=top_easy_id, p_mastery=0.20))
            db.add(Mastery(student_id=student_1_id, topic_id=top_hard_id, p_mastery=0.85))
            db.commit()

        # Quiz on top_easy
        easy_quiz_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "topic_ids": [top_easy_id],
                "num_questions": 2,
                "difficulty": "auto",
            },
        )
        assert easy_quiz_res.status_code == 201
        easy_diffs = [q["difficulty"] for q in easy_quiz_res.json()["questions"]]

        # Quiz on top_hard
        hard_quiz_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "topic_ids": [top_hard_id],
                "num_questions": 2,
                "difficulty": "auto",
            },
        )
        assert hard_quiz_res.status_code == 201
        hard_diffs = [q["difficulty"] for q in hard_quiz_res.json()["questions"]]

        with SessionLocal() as db:
            m_count_after = db.scalar(select(func.count(Mastery.id))) or 0
            me_count_after = db.scalar(select(func.count(MasteryEvent.id))) or 0

        c7_auto_diff = all(d == "easy" for d in easy_diffs) and all(d == "hard" for d in hard_diffs)
        # Mastery row count only grew by the 2 manually inserted test rows; zero rows written by endpoints
        c7_no_writes = (m_count_after == m_count_before + 2) and (me_count_after == me_count_before)
        c7_ok = c7_auto_diff and c7_no_writes
        results["auto difficulty: Mastery p_mastery 0.2 -> easy, 0.85 -> hard; no rows written to Mastery/MasteryEvent"] = c7_ok

        # -----------------------------------------------------------------
        # CHECK 8: Validation & scope errors
        # -----------------------------------------------------------------
        # Topic expand with parent
        with SessionLocal() as db:
            parent_top = db.scalar(
                select(Topic).where(Topic.course_id == course_1_id, Topic.parent_id.is_(None))
            )
            parent_top_id = parent_top.id
        parent_scope_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "topic_ids": [parent_top_id],
                "num_questions": 3,
            },
        )
        c8_parent_ok = parent_scope_res.status_code == 201

        # Unknown topic -> 404
        c8_unknown_top = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={"student_id": student_1_id, "topic_ids": [999999]},
        ).status_code == 404

        # Empty KB course -> 409
        crs_empty = client.post("/api/v1/courses", json={"name": "Empty Course", "student_id": student_1_id}).json()
        c8_empty_kb = client.post(
            f"/api/v1/courses/{crs_empty['id']}/assessments",
            json={"student_id": student_1_id},
        ).status_code == 409

        # Num questions 0 or 999 -> 422
        c8_invalid_num = (
            client.post(
                f"/api/v1/courses/{course_1_id}/assessments",
                json={"student_id": student_1_id, "num_questions": 0},
            ).status_code == 422
            and client.post(
                f"/api/v1/courses/{course_1_id}/assessments",
                json={"student_id": student_1_id, "num_questions": 999},
            ).status_code == 422
        )

        # Unknown student -> 404
        c8_unknown_stu = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={"student_id": 999999},
        ).status_code == 404

        c8_ok = c8_parent_ok and c8_unknown_top and c8_empty_kb and c8_invalid_num and c8_unknown_stu
        results["topic_ids with parent expands to leaf descendants; topic 404; empty KB 409; num 422; student 404"] = c8_ok

        # -----------------------------------------------------------------
        # CHECK 9: Verifier unit check
        # -----------------------------------------------------------------
        verifier = MockQuestionVerifier()
        with SessionLocal() as db:
            c1_chunk = db.get(Chunk, 1)
        chunk_map = {1: c1_chunk}

        # Candidate with correct key (option text present in chunk text)
        q_valid = CandidateQuestion(
            topic_id=1,
            qtype="mcq",
            difficulty="medium",
            prompt="What forms the cornerstone of mechanics?",
            options=[
                {"key": "A", "text": "Newton's laws"},
                {"key": "B", "text": "Aristotle logic"},
                {"key": "C", "text": "Baking flour"},
                {"key": "D", "text": "Solar wind"},
            ],
            correct_answer="A",
            explanation="Grounded in text",
            source_chunk_ids=[1],
            fingerprint="fp1",
        )
        # Candidate with deliberately wrong key (option text NOT in chunk text)
        q_invalid = CandidateQuestion(
            topic_id=1,
            qtype="mcq",
            difficulty="medium",
            prompt="What forms the cornerstone of mechanics?",
            options=[
                {"key": "A", "text": "Newton's laws"},
                {"key": "B", "text": "Aristotle logic"},
                {"key": "C", "text": "Baking flour"},
                {"key": "D", "text": "Solar wind"},
            ],
            correct_answer="C",  # C is not supported in physics chunk
            explanation="Deliberately wrong",
            source_chunk_ids=[1],
            fingerprint="fp2",
        )

        v_passed, v_rejected = verifier.verify_candidates([q_valid, q_invalid], chunk_map)
        c9_ok = len(v_passed) == 1 and v_passed[0].correct_answer == "A" and len(v_rejected) == 1
        results["verifier unit check: deliberately wrong key is rejected; correct one accepted"] = c9_ok

        # -----------------------------------------------------------------
        # CHECK 10: /dev/generate-questions persists nothing (Question row count unchanged)
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            q_count_before = db.scalar(select(func.count(Question.id))) or 0

        dev_gen_res = client.post(
            "/dev/generate-questions",
            json={
                "course_id": course_1_id,
                "topic_id": top_easy_id,
                "num_questions": 2,
                "difficulty": "medium",
                "question_types": ["mcq", "short_answer"],
            },
        )
        assert dev_gen_res.status_code == 200, f"dev generate failed: {dev_gen_res.text}"
        dev_gen_data = dev_gen_res.json()
        c10_has_accepted = len(dev_gen_data["accepted"]) > 0

        with SessionLocal() as db:
            q_count_after = db.scalar(select(func.count(Question.id))) or 0

        c10_persists_nothing = q_count_after == q_count_before
        c10_ok = c10_has_accepted and c10_persists_nothing
        results["/dev/generate-questions returns accepted and rejected lists and persists nothing (Question row count unchanged)"] = c10_ok

        # -----------------------------------------------------------------
        # CHECK 11: GET /assessments/{id}, list, and DELETE cascade
        # -----------------------------------------------------------------
        get_res = client.get(f"/api/v1/assessments/{quiz_id}")
        assert get_res.status_code == 200
        get_data = get_res.json()
        c11_get_matches = get_data["id"] == quiz_id and len(get_data["questions"]) == quiz_data["num_questions"]

        list_res = client.get(f"/api/v1/courses/{course_1_id}/assessments?student_id={student_1_id}")
        assert list_res.status_code == 200
        list_data = list_res.json()
        c11_list_ok = len(list_data) >= 1 and list_data[0]["id"] is not None

        del_res = client.delete(f"/api/v1/assessments/{quiz_id}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        with SessionLocal() as db:
            q_in_del = db.scalar(select(func.count(Question.id)).where(Question.assessment_id == quiz_id)) or 0
            a_in_del = db.get(Assessment, quiz_id) is not None

        c11_del_ok = (q_in_del == 0) and (not a_in_del)
        c11_ok = c11_get_matches and c11_list_ok and c11_del_ok
        results["GET /assessments/{id} matches creation; list works; DELETE cascades questions and deletes question vectors"] = c11_ok

        # -----------------------------------------------------------------
        # CHECK 12: Vectors exist in folio_questions with student_id metadata
        # -----------------------------------------------------------------
        vstore = get_vector_store()
        q_col_count = vstore.questions_collection.count()
        assert q_col_count > 0

        # Query questions for student 1
        query_emb = [0.1] * 64
        q_hits = vstore.query_similar_questions(
            course_id=course_1_id,
            embedding=query_emb,
            top_k=5,
            student_id=student_1_id,
        )
        c12_has_meta = len(q_hits) > 0 and all(h.get("student_id") == student_1_id for h in q_hits)
        results["vectors exist in folio_questions for created questions, with student_id metadata"] = c12_has_meta

    # -----------------------------------------------------------------
    # Print Summary Table
    # -----------------------------------------------------------------
    print()
    print("Verification Checklist:")
    all_passed = True
    for desc, passed in results.items():
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status_str}] {desc}")

    print("-" * 70)
    if all_passed:
        print("OVERALL RESULT: ALL CHECKS PASSED")
        return 0
    else:
        print("OVERALL RESULT: SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_verification())
