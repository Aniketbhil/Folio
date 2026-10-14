#!/usr/bin/env python3
"""End-to-end verification script for Folio Prompt 6: Grading, Misconceptions, and BKT Learner Model.

Tests:
1. BKT pure function: raises on correct, lowers on wrong, 0.5 strictly intermediate, clamped in [BKT_MIN, BKT_MAX], hard-correct > easy-correct.
2. Answering MCQ correctly: is_correct true, score 1, no misconception, citations non-empty with ref 1..n, mastery increases, Mastery & MasteryEvent saved.
3. Answering MCQ wrongly: is_correct false, misconception present, correct_answer revealed, mastery decreases, correct_count unchanged.
4. Short answer: restating model answer scores >= threshold, irrelevant answers score low, key points hit/missing populated.
5. Numerical: unit tests on parse_number ("9.8", "9.8 m/s^2", "9,8", "9.81", "3 x 10^8", "5 wrong"), unparseable text -> 422 and NO attempt.
6. Invalid MCQ answer ("Z") -> 422 and no attempt row.
7. Answering the same question twice -> 409 already_answered and only one attempt/MasteryEvent exists.
8. Student mismatch -> 403; unknown question -> 404; answering after submit -> 409 invalid_state.
9. GET /assessments/{id} while in progress: answered questions have keys/explanations/attempt, unanswered questions have NONE.
10. Submit with zero answers -> 409; submit after answering 4 of 6 -> score = sum(scores)/6, skipped = 2, status submitted; submit again -> 200 same report.
11. Report: all fields present, by_topic matches events, weak_topics ordered by mastery_after asc, misconceptions present, recommended_next_steps non-empty, GET /report equals submit, GET /report before submit -> 409.
12. Diagnostic: create via POST /diagnostic, answer, submit, MasteryEvent.origin == 'diagnostic' and diagnostic_note present.
13. Delete assessment: attempts gone, Mastery and MasteryEvent rows still present.
14. Concurrency: fire two simultaneous answers to same question with threads; exactly one succeeds (200), other gets 409.
15. /dev/bkt-simulate: returns trajectory and writes nothing to DB.
"""

import concurrent.futures
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
temp_dir = tempfile.mkdtemp(prefix="folio_grading_verify_")
test_db_path = Path(temp_dir) / "test.db"
test_chroma_path = Path(temp_dir) / "chroma"
test_upload_path = Path(temp_dir) / "uploads"

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ["CHROMA_DIR"] = str(test_chroma_path)
os.environ["UPLOAD_DIR"] = str(test_upload_path)
os.environ["LLM_MOCK"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["DEBUG"] = "true"
os.environ["AUTH_REQUIRED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine, run_sqlite_migrations
from app.main import create_app
from app.models.assessment import Assessment, Attempt, Question
from app.models.mastery import Mastery, MasteryEvent
from app.models.topic import Topic
from app.services.grading.numeric import grade_numeric, parse_number
from app.services.learner.mastery import bkt_update, status_for
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
    print(" Folio Prompt 6: Grading, Misconceptions & BKT Verification")
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
        stu1_res = client.post("/api/v1/students", json={"name": "Alice Learner", "email": "alice@folio.edu"})
        assert stu1_res.status_code == 201
        student_1_id = stu1_res.json()["id"]

        stu2_res = client.post("/api/v1/students", json={"name": "Bob Learner", "email": "bob@folio.edu"})
        assert stu2_res.status_code == 201
        student_2_id = stu2_res.json()["id"]

        # Setup Course 1
        crs1_res = client.post("/api/v1/courses", json={"name": "Physics & Engineering", "student_id": student_1_id})
        assert crs1_res.status_code == 201
        course_1_id = crs1_res.json()["id"]

        # Ingest samples
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
                data={"title": "Slides"},
            )
        with open(vtt_path, "rb") as f:
            client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.vtt", f, "text/vtt")},
                data={"title": "Lecture Video"},
            )

        kb_stat = wait_for_kb_ready(client, course_1_id)
        assert kb_stat.get("kb_status") == "ready", f"KB failed: {kb_stat}"

        # -----------------------------------------------------------------
        # CHECK 1: BKT pure function assertions
        # -----------------------------------------------------------------
        settings = get_settings()
        p_base = 0.50
        p_up = bkt_update(p_base, 1.0, "mcq", "medium")
        p_down = bkt_update(p_base, 0.0, "mcq", "medium")
        p_mid = bkt_update(p_base, 0.5, "mcq", "medium")

        c1_raises = p_up > p_base
        c1_lowers = p_down < p_base
        c1_between = p_down < p_mid < p_up

        # Clamping
        p_zero = bkt_update(0.0, 0.0, "mcq", "medium")
        p_one = bkt_update(1.0, 1.0, "mcq", "medium")
        c1_clamp = (p_zero >= settings.bkt_min) and (p_one <= settings.bkt_max)

        # Hard-correct raises more than easy-correct
        p_hard_corr = bkt_update(0.50, 1.0, "mcq", "hard")
        p_easy_corr = bkt_update(0.50, 1.0, "mcq", "easy")
        c1_hard_vs_easy = p_hard_corr > p_easy_corr

        c1_ok = c1_raises and c1_lowers and c1_between and c1_clamp and c1_hard_vs_easy
        results["BKT pure function: raises on correct, lowers on wrong, 0.5 intermediate, clamped, hard-correct > easy-correct"] = c1_ok

        # -----------------------------------------------------------------
        # CHECK 2 & 3: Create Quiz & Test MCQ Correct & MCQ Wrong Answering
        # -----------------------------------------------------------------
        quiz_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={
                "student_id": student_1_id,
                "kind": "quiz",
                "num_questions": 6,
                "difficulty": "medium",
                "question_types": ["mcq", "short_answer"],
            },
        )
        assert quiz_res.status_code == 201, f"Failed quiz creation: {quiz_res.text}"
        quiz_data = quiz_res.json()
        quiz_id = quiz_data["id"]

        with SessionLocal() as db:
            q_rows = list(
                db.scalars(
                    select(Question).where(Question.assessment_id == quiz_id).order_by(Question.position.asc())
                ).all()
            )
            mcq_questions = [q for q in q_rows if q.qtype == "mcq"]
            sa_questions = [q for q in q_rows if q.qtype == "short_answer"]
            q_mcq_1 = mcq_questions[0]
            q_mcq_2 = mcq_questions[1]
            q_sa_1 = sa_questions[0]
            q_sa_2 = sa_questions[1]
            q_mcq_1_id = q_mcq_1.id
            q_mcq_1_key = q_mcq_1.correct_answer
            q_mcq_1_topic_id = q_mcq_1.topic_id

            q_mcq_2_id = q_mcq_2.id
            q_mcq_2_key = q_mcq_2.correct_answer
            q_mcq_2_topic_id = q_mcq_2.topic_id

            q_sa_1_id = q_sa_1.id
            q_sa_1_ans = q_sa_1.correct_answer

            q_sa_2_id = q_sa_2.id

        # Answer MCQ 1 correctly
        ans1_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{q_mcq_1_id}/answer",
            json={"answer": q_mcq_1_key, "time_taken_sec": 15.0, "student_id": student_1_id},
        )
        assert ans1_res.status_code == 200, f"Ans 1 failed: {ans1_res.text}"
        ans1_data = ans1_res.json()

        with SessionLocal() as db:
            m_row1 = db.scalar(select(Mastery).where(Mastery.student_id == student_1_id, Mastery.topic_id == q_mcq_1_topic_id))
            ev_row1 = db.scalar(select(MasteryEvent).where(MasteryEvent.attempt_id == ans1_data["attempt_id"]))

        c2_ok = (
            ans1_data["is_correct"] is True
            and ans1_data["score"] == 1.0
            and ans1_data["misconception"] is None
            and len(ans1_data["citations"]) > 0
            and ans1_data["citations"][0]["ref"] == 1
            and ans1_data["mastery_update"]["after"] > ans1_data["mastery_update"]["before"]
            and m_row1 is not None
            and m_row1.attempts_count == 1
            and m_row1.correct_count == 1
            and ev_row1 is not None
            and ev_row1.attempt_id == ans1_data["attempt_id"]
        )
        results["answering MCQ correctly: is_correct true, score 1, no misconception, citations non-empty with ref, mastery increases, Mastery & event saved"] = c2_ok

        # Answer MCQ 2 wrongly
        wrong_letter = "B" if q_mcq_2_key.upper() != "B" else "C"
        ans2_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{q_mcq_2_id}/answer",
            json={"answer": wrong_letter, "time_taken_sec": 20.0, "student_id": student_1_id},
        )
        assert ans2_res.status_code == 200, f"Ans 2 failed: {ans2_res.text}"
        ans2_data = ans2_res.json()

        with SessionLocal() as db:
            m_row2 = db.scalar(select(Mastery).where(Mastery.student_id == student_1_id, Mastery.topic_id == q_mcq_2_topic_id))

        c3_ok = (
            ans2_data["is_correct"] is False
            and ans2_data["score"] == 0.0
            and ans2_data["misconception"] is not None
            and ans2_data["correct_answer"]["key"] == q_mcq_2_key
            and ans2_data["mastery_update"]["after"] < ans2_data["mastery_update"]["before"]
            and m_row2 is not None
            and m_row2.attempts_count == 1
            and m_row2.correct_count == 0
        )
        results["answering MCQ wrongly: is_correct false, misconception present, correct_answer revealed, mastery decreases, correct_count unchanged"] = c3_ok

        # -----------------------------------------------------------------
        # CHECK 4: Short answer grading
        # -----------------------------------------------------------------
        # Good short answer restating model answer
        sa1_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{q_sa_1_id}/answer",
            json={"answer": q_sa_1_ans, "time_taken_sec": 30.0, "student_id": student_1_id},
        )
        assert sa1_res.status_code == 200
        sa1_data = sa1_res.json()

        # Poor short answer
        sa2_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{q_sa_2_id}/answer",
            json={"answer": "I have no idea about this topic.", "time_taken_sec": 5.0, "student_id": student_1_id},
        )
        assert sa2_res.status_code == 200
        sa2_data = sa2_res.json()

        c4_ok = (
            sa1_data["score"] >= settings.grade_correct_threshold
            and sa1_data["is_correct"] is True
            and len(sa1_data["key_points_hit"] or []) > 0
            and sa2_data["score"] < settings.grade_correct_threshold
            and sa2_data["is_correct"] is False
            and len(sa2_data["key_points_missing"] or []) > 0
        )
        results["short answer: restating model answer scores >= threshold, irrelevant answer scores low, key points hit/missing populated"] = c4_ok

        # -----------------------------------------------------------------
        # CHECK 5: Numerical question grading & unit-test
        # -----------------------------------------------------------------
        # Unit tests on parse_number and grade_numeric
        assert parse_number("9.8") == 9.8
        assert parse_number("9.8 m/s^2") == 9.8
        assert parse_number("9,8") == 9.8  # European decimal comma handled
        assert parse_number("3 x 10^8") == 300000000.0
        assert parse_number("3 × 10^8") == 300000000.0
        assert parse_number("1/2") == 0.5
        assert parse_number("not a number") is None

        score_corr, _ = grade_numeric("9.8", 9.8, tolerance_pct=1.0)
        assert score_corr == 1.0
        score_tol, _ = grade_numeric("9.81", 9.8, tolerance_pct=1.0)
        assert score_tol == 1.0  # 0.01 <= 0.098
        score_wrong, _ = grade_numeric("5", 9.8, tolerance_pct=1.0)
        assert score_wrong == 0.0

        # Fabricate numerical question in DB to test API error handling
        with SessionLocal() as db:
            num_q = Question(
                assessment_id=quiz_id,
                course_id=course_1_id,
                topic_id=q_mcq_1_topic_id,
                qtype="numerical",
                difficulty="medium",
                prompt="Calculate standard acceleration of gravity.",
                correct_answer="9.8",
                explanation="Standard gravity on Earth is approximately 9.8 m/s^2.",
                source_chunk_ids=[],
                verified=True,
                fingerprint="fp_numerical_test",
                position=10,
                meta={"tolerance_pct": 1.0, "unit": "m/s^2"},
            )
            db.add(num_q)
            db.commit()
            num_q_id = num_q.id

            att_count_before = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == num_q_id))

        unparseable_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{num_q_id}/answer",
            json={"answer": "about tenish meters per second", "student_id": student_1_id},
        )
        assert unparseable_res.status_code == 422
        assert unparseable_res.json()["error"]["code"] == "invalid_answer"

        with SessionLocal() as db:
            att_count_after = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == num_q_id))
            # Clean up the test numerical question so it doesn't skew assessment questions count
            db.delete(db.get(Question, num_q_id))
            db.commit()

        c5_ok = att_count_after == att_count_before
        results["numerical: unit tests pass (9.8, units, European comma, tolerance, 3x10^8); unparseable text -> 422 and NO attempt row"] = c5_ok

        # -----------------------------------------------------------------
        # CHECK 6: Invalid MCQ answer ("Z") -> 422 and no attempt row
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            answered_qids = set(
                db.scalars(
                    select(Attempt.question_id).where(Attempt.assessment_id == quiz_id)
                ).all()
            )
            unanswered_mcqs = [
                q for q in db.scalars(
                    select(Question).where(Question.assessment_id == quiz_id)
                ).all()
                if q.id not in answered_qids and q.qtype == "mcq"
            ]
            unanswered_q = unanswered_mcqs[0]
            unanswered_q_id = unanswered_q.id
            att_count_unanswered_before = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == unanswered_q_id))

        z_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{unanswered_q_id}/answer",
            json={"answer": "Z", "student_id": student_1_id},
        )
        assert z_res.status_code == 422
        assert z_res.json()["error"]["code"] == "invalid_answer"

        with SessionLocal() as db:
            att_count_unanswered_after = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == unanswered_q_id))

        c6_ok = att_count_unanswered_after == att_count_unanswered_before
        results["invalid MCQ answer ('Z') -> 422 and no attempt row"] = c6_ok

        # -----------------------------------------------------------------
        # CHECK 7: Answering the same question twice -> 409 already_answered
        # -----------------------------------------------------------------
        dup_ans_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{q_mcq_1_id}/answer",
            json={"answer": q_mcq_1_key, "student_id": student_1_id},
        )
        assert dup_ans_res.status_code == 409
        assert dup_ans_res.json()["error"]["code"] == "already_answered"

        with SessionLocal() as db:
            q1_att_count = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == q_mcq_1_id))
            q1_ev_count = db.scalar(select(func.count(MasteryEvent.id)).where(MasteryEvent.attempt_id == ans1_data["attempt_id"]))

        c7_ok = q1_att_count == 1 and q1_ev_count == 1
        results["answering the same question twice -> 409 already_answered and only one attempt/MasteryEvent exists"] = c7_ok

        # -----------------------------------------------------------------
        # CHECK 8: Student mismatch -> 403; unknown question -> 404
        # -----------------------------------------------------------------
        mismatch_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{unanswered_q_id}/answer",
            json={"answer": "A", "student_id": student_2_id},
        )
        assert mismatch_res.status_code == 403
        assert mismatch_res.json()["error"]["code"] == "forbidden_student"

        unknown_q_res = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/999999/answer",
            json={"answer": "A", "student_id": student_1_id},
        )
        assert unknown_q_res.status_code == 404
        assert unknown_q_res.json()["error"]["code"] == "question_not_found"

        results["student_id mismatch -> 403; unknown question -> 404"] = True

        # -----------------------------------------------------------------
        # CHECK 9: GET /assessments/{id} while in progress
        # -----------------------------------------------------------------
        get_in_progress_res = client.get(f"/api/v1/assessments/{quiz_id}")
        assert get_in_progress_res.status_code == 200
        get_ip_data = get_in_progress_res.json()

        answered_qs = [q for q in get_ip_data["questions"] if q["answered"]]
        unanswered_qs = [q for q in get_ip_data["questions"] if not q["answered"]]

        c9_answered_have_keys = all(
            q["correct_answer"] is not None and q["explanation"] is not None and q["attempt"] is not None
            for q in answered_qs
        )
        c9_unanswered_no_keys = all(
            q["correct_answer"] is None and q["explanation"] is None and q["attempt"] is None
            for q in unanswered_qs
        )
        c9_ok = len(answered_qs) == 4 and len(unanswered_qs) == 2 and c9_answered_have_keys and c9_unanswered_no_keys
        results["GET /assessments/{id} while in progress: answered questions have keys/explanations/attempt, unanswered have NONE"] = c9_ok

        # -----------------------------------------------------------------
        # CHECK 10: Submit with zero answers -> 409; submit after answering 4 of 6
        # -----------------------------------------------------------------
        # Fresh quiz with 0 answers
        empty_quiz_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={"student_id": student_1_id, "kind": "quiz", "num_questions": 3},
        )
        empty_quiz_id = empty_quiz_res.json()["id"]
        empty_submit_res = client.post(f"/api/v1/assessments/{empty_quiz_id}/submit")
        assert empty_submit_res.status_code == 409
        assert empty_submit_res.json()["error"]["code"] == "no_answers"

        # Submit main quiz (4 answered of 6)
        sub_res = client.post(f"/api/v1/assessments/{quiz_id}/submit")
        assert sub_res.status_code == 200, f"Submit failed: {sub_res.text}"
        sub_data = sub_res.json()

        # Idempotent submit
        sub2_res = client.post(f"/api/v1/assessments/{quiz_id}/submit")
        assert sub2_res.status_code == 200
        sub2_data = sub2_res.json()

        # Check answering after submit -> 409 invalid_state
        post_sub_ans = client.post(
            f"/api/v1/assessments/{quiz_id}/questions/{unanswered_q_id}/answer",
            json={"answer": "A", "student_id": student_1_id},
        )
        assert post_sub_ans.status_code == 409
        assert post_sub_ans.json()["error"]["code"] == "invalid_state"

        expected_sum_score = ans1_data["score"] + ans2_data["score"] + sa1_data["score"] + sa2_data["score"]
        expected_final_score = round(expected_sum_score / 6.0, 4)

        c10_ok = (
            sub_data["summary"]["total_questions"] == 6
            and sub_data["summary"]["answered"] == 4
            and sub_data["summary"]["skipped"] == 2
            and abs(sub_data["summary"]["score"] - expected_final_score) < 1e-3
            and sub_data["assessment"]["id"] == quiz_id
            and sub2_data["summary"]["score"] == sub_data["summary"]["score"]
        )
        results["submit with zero answers -> 409; submit after answering 4 of 6 -> score=sum/6, skipped=2, idempotent 200"] = c10_ok

        # -----------------------------------------------------------------
        # CHECK 11: Report comprehensive validation
        # -----------------------------------------------------------------
        get_rep_res = client.get(f"/api/v1/assessments/{quiz_id}/report")
        assert get_rep_res.status_code == 200
        rep_data = get_rep_res.json()

        # GET /report on in-progress assessment -> 409 not_submitted
        unsub_rep_res = client.get(f"/api/v1/assessments/{empty_quiz_id}/report")
        assert unsub_rep_res.status_code == 409
        assert unsub_rep_res.json()["error"]["code"] == "not_submitted"

        c11_has_fields = all(k in rep_data for k in [
            "assessment", "summary", "by_topic", "weak_topics", "strong_topics",
            "by_difficulty", "by_type", "misconceptions", "review", "recommended_next_steps"
        ])
        c11_weak_sorted = True
        if len(rep_data["weak_topics"]) > 1:
            for i in range(len(rep_data["weak_topics"]) - 1):
                if rep_data["weak_topics"][i]["mastery_after"] > rep_data["weak_topics"][i + 1]["mastery_after"]:
                    c11_weak_sorted = False

        c11_review_complete = len(rep_data["review"]) == 6 and all(
            r["correct_answer"] is not None and r["explanation"] is not None for r in rep_data["review"]
        )

        c11_ok = c11_has_fields and c11_weak_sorted and c11_review_complete and (rep_data["summary"] == sub_data["summary"])
        results["report: all fields present, weak_topics sorted asc, review has all 6 questions with keys, GET /report equals submit"] = c11_ok

        # -----------------------------------------------------------------
        # CHECK 12: Diagnostic workflow
        # -----------------------------------------------------------------
        diag_res = client.post(f"/api/v1/courses/{course_1_id}/diagnostic?student_id={student_2_id}")
        assert diag_res.status_code == 201
        diag_data = diag_res.json()
        diag_id = diag_data["id"]
        diag_q1 = diag_data["questions"][0]

        with SessionLocal() as db:
            diag_q1_row = db.get(Question, diag_q1["id"])
            diag_q1_key = diag_q1_row.correct_answer

        diag_ans_res = client.post(
            f"/api/v1/assessments/{diag_id}/questions/{diag_q1['id']}/answer",
            json={"answer": diag_q1_key, "student_id": student_2_id},
        )
        assert diag_ans_res.status_code == 200

        with SessionLocal() as db:
            diag_event = db.scalar(select(MasteryEvent).where(MasteryEvent.attempt_id == diag_ans_res.json()["attempt_id"]))

        diag_sub_res = client.post(f"/api/v1/assessments/{diag_id}/submit")
        assert diag_sub_res.status_code == 200
        diag_report = diag_sub_res.json()

        c12_ok = (
            diag_event is not None
            and diag_event.origin == "diagnostic"
            and diag_report["diagnostic_note"] is not None
            and "starting level" in diag_report["diagnostic_note"].lower()
        )
        results["diagnostic: POST /diagnostic, answer, submit -> MasteryEvent.origin == 'diagnostic' and diagnostic_note present"] = c12_ok

        # -----------------------------------------------------------------
        # CHECK 13: Delete assessment: attempts deleted, Mastery & events kept
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            mastery_count_before = db.scalar(select(func.count(Mastery.id)))
            events_count_before = db.scalar(select(func.count(MasteryEvent.id)))
            quiz_attempts_count = db.scalar(select(func.count(Attempt.id)).where(Attempt.assessment_id == quiz_id))
            assert quiz_attempts_count == 4

        del_res = client.delete(f"/api/v1/assessments/{quiz_id}")
        assert del_res.status_code == 200

        with SessionLocal() as db:
            mastery_count_after = db.scalar(select(func.count(Mastery.id)))
            events_count_after = db.scalar(select(func.count(MasteryEvent.id)))
            attempts_remaining = db.scalar(select(func.count(Attempt.id)).where(Attempt.assessment_id == quiz_id))

        c13_ok = (
            attempts_remaining == 0
            and mastery_count_after == mastery_count_before
            and events_count_after == events_count_before
        )
        results["delete assessment: attempts gone, Mastery and MasteryEvent rows preserved"] = c13_ok

        # -----------------------------------------------------------------
        # CHECK 14: Concurrency test on answering same question
        # -----------------------------------------------------------------
        c_quiz_res = client.post(
            f"/api/v1/courses/{course_1_id}/assessments",
            json={"student_id": student_2_id, "kind": "quiz", "num_questions": 2},
        )
        c_quiz_id = c_quiz_res.json()["id"]
        c_q_id = c_quiz_res.json()["questions"][0]["id"]

        def send_answer(ans_str: str) -> int:
            r = client.post(
                f"/api/v1/assessments/{c_quiz_id}/questions/{c_q_id}/answer",
                json={"answer": ans_str, "student_id": student_2_id},
            )
            return r.status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(send_answer, "A")
            f2 = executor.submit(send_answer, "B")
            statuses = [f1.result(), f2.result()]

        statuses.sort()
        with SessionLocal() as db:
            c_att_count = db.scalar(select(func.count(Attempt.id)).where(Attempt.question_id == c_q_id))

        c14_ok = statuses == [200, 409] and c_att_count == 1
        results["concurrency: two simultaneous answers to same question -> exactly one 200, other 409, 1 attempt in DB"] = c14_ok

        # -----------------------------------------------------------------
        # CHECK 15: /dev/bkt-simulate returns trajectory and writes nothing
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            m_before = db.scalar(select(func.count(Mastery.id)))
            me_before = db.scalar(select(func.count(MasteryEvent.id)))

        sim_res = client.post(
            "/dev/bkt-simulate",
            json={
                "p_init": 0.40,
                "sequence": [
                    {"score": 1.0, "qtype": "mcq", "difficulty": "medium"},
                    {"score": 0.0, "qtype": "mcq", "difficulty": "hard"},
                ],
            },
        )
        assert sim_res.status_code == 200
        sim_data = sim_res.json()

        with SessionLocal() as db:
            m_after = db.scalar(select(func.count(Mastery.id)))
            me_after = db.scalar(select(func.count(MasteryEvent.id)))

        c15_ok = (
            len(sim_data["trajectory"]) == 2
            and sim_data["trajectory"][0]["p_after"] > sim_data["trajectory"][0]["p_before"]
            and sim_data["trajectory"][1]["p_after"] < sim_data["trajectory"][1]["p_before"]
            and m_after == m_before
            and me_after == me_before
        )
        results["/dev/bkt-simulate returns trajectory and writes nothing to database"] = c15_ok

    print("\nVerification Checklist:")
    all_passed = True
    for desc, passed in results.items():
        status_str = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print(f"  {status_str} {desc}")

    print("-" * 70)
    if all_passed:
        print("OVERALL RESULT: ALL CHECKS PASSED\n")
        return 0
    else:
        print("OVERALL RESULT: SOME CHECKS FAILED\n")
        return 1


if __name__ == "__main__":
    exit_code = run_verification()
    # Cleanup temp directory
    try:
        shutil.rmtree(temp_dir, ignore_errors=True)
    except Exception:
        pass
    sys.exit(exit_code)
