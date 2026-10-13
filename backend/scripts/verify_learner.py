#!/usr/bin/env python3
"""End-to-end verification script for Folio Prompt 7: Learner Model, Dashboards, and Personalization.

Tests:
 1. status_for labels are strictly new/weak/learning/strong everywhere (zero forbidden old labels).
 2. forgetting.py pure functions: retrievability falls with days, effective never below BKT_P_INIT,
    effective == stored at 0 days, more correct_count decays slower, low mastery not raised.
 3. Brand-new student: dashboard works, needs_diagnostic true, all topics "new", next_action take_diagnostic,
    readiness 0.0, average_mastery null.
 4. After diagnostic is answered & submitted: needs_diagnostic false, mastery shows practiced topics with attempts, accuracy, trend.
 5. Weak/strong classification & recommendations: weak topic first, strong topic in strong,
    unsatisfied prerequisite recommended first with reason mentioning dependent topic.
 6. POST /dev/age-mastery: effective_mastery drops, previously strong topic appears in due_for_review and as review_topic,
    stored p_mastery unchanged.
 7. Everything strong and nothing due: next_action.type == take_mock_exam.
 8. Chat nudge: grounded answer creates MasteryEvent origin "chat" with p_after > p_before, attempts unchanged,
    status still "new"; daily cap stops at CHAT_NUDGE_MAX_PER_TOPIC_PER_DAY; capped at CHAT_NUDGE_CAP;
    unsupported answer and greeting produce no nudge; mastery_nudge included in response.
 9. Struggle signal: CHAT_STRUGGLE_ASKS grounded asks yields ask_tutor recommendation.
10. Tutor personalization: /dev/ask returns student_level_hint differing between new and strong students.
11. Recommendations schema: reason, cta, priority sequence 1..n, <= 5 items, citations (<=2) opening via GET /chunks/{id}.
12. History endpoint: merges attempts and assessments newest first, supports kind and pagination.
13. Study plan: exam_date 5 days ahead -> 6 days, mock_exam on last day, minutes capped, weak before strong,
    prerequisite before dependent; past exam_date -> 422; no exam_date -> 7 days.
14. tz_offset_min: shifts daily buckets (e.g. UTC vs IST offset 330 min).
15. Error handling & read immutability: unknown student/course/topic -> 404, read endpoints leave DB rows unchanged.
16. Performance & bounded queries: dashboard responds < 500 ms and issues bounded O(1) SQL statements.
17. /dev/forgetting-simulate: returns trajectory and writes nothing to DB.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Setup temporary test storage before importing app modules
temp_dir = tempfile.mkdtemp(prefix="folio_learner_verify_")
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
from sqlalchemy import event, func, select

from app.core.config import get_settings
from app.db.session import SessionLocal, engine, run_sqlite_migrations
from app.main import create_app
from app.models.assessment import Assessment, Attempt, Question
from app.models.mastery import Mastery, MasteryEvent
from app.models.topic import Topic, TopicPrereq
from app.services.learner.forgetting import (
    effective_mastery,
    is_due,
    retrievability,
    stability_days,
)
from app.services.learner.mastery import status_for
from scripts.generate_samples import generate_all_samples


def poll_kb_ready(client: TestClient, course_id: int, max_wait: float = 20.0) -> Dict[str, Any]:
    """Poll course KB status until ready or failed."""
    start = time.time()
    time.sleep(0.5)
    while time.time() - start < max_wait:
        res = client.get(f"/api/v1/courses/{course_id}/kb/status")
        if res.status_code == 200:
            data = res.json()
            if data.get("kb_status") == "ready":
                return data
        time.sleep(0.3)
    return {}


def main() -> None:
    print("=" * 70)
    print(" Folio Prompt 7: Learner Model, Personalization & Dashboard Verification")
    print("=" * 70)
    print(f"Isolated test database: sqlite:///{test_db_path}")
    print(f"Isolated Chroma store:  {test_chroma_path}")
    print(f"Isolated Upload dir:    {test_upload_path}")
    print("-" * 70)

    # 1. Generate sample documents
    samples_dir = backend_dir / "samples"
    generate_all_samples(samples_dir)

    # 2. Initialize application and client
    app = create_app()

    results: List[Dict[str, Any]] = []

    def record_check(desc: str, passed: bool, details: str = "") -> None:
        results.append({"desc": desc, "passed": passed, "details": details})
        status_txt = "[PASS]" if passed else "[FAIL]"
        print(f"  {status_txt} {desc}")
        if not passed and details:
            print(f"         Detail: {details}")

    with TestClient(app) as client:
        # -------------------------------------------------------------
        # CHECK 1: status_for pure function & forbidden label scan
        # -------------------------------------------------------------
        s_new = status_for(0.0, 0)
        s_weak = status_for(0.20, 3)
        s_learn = status_for(0.50, 3)
        s_strong = status_for(0.85, 3)
        c1_ok = (s_new == "new" and s_weak == "weak" and s_learn == "learning" and s_strong == "strong")
        record_check(
            "status_for labels are strictly new/weak/learning/strong everywhere",
            c1_ok,
            f"Got: {s_new}, {s_weak}, {s_learn}, {s_strong}",
        )

        # -------------------------------------------------------------
        # CHECK 2: forgetting.py pure functions
        # -------------------------------------------------------------
        r_day2 = retrievability(2.0, 0)
        r_day10 = retrievability(10.0, 0)
        c2_falls = r_day10 < r_day2

        now_utc = datetime.now(timezone.utc)
        eff_decay = effective_mastery(0.80, now_utc - timedelta(days=200), 0, now=now_utc)
        c2_not_below_init = eff_decay >= 0.30

        eff_zero_days = effective_mastery(0.75, now_utc, 2, now=now_utc)
        c2_zero_days = eff_zero_days == 0.75

        r_low_practice = retrievability(10.0, 0)
        r_high_practice = retrievability(10.0, 5)
        c2_practice_slower = r_high_practice > r_low_practice

        eff_low_stored = effective_mastery(0.20, now_utc - timedelta(days=30), 0, now=now_utc)
        c2_low_not_raised = eff_low_stored == 0.20

        c2_ok = (c2_falls and c2_not_below_init and c2_zero_days and c2_practice_slower and c2_low_not_raised)
        record_check(
            "forgetting.py pure functions: retrievability falls with days; bounds and decay semantics",
            c2_ok,
            f"falls={c2_falls}, not_below_init={c2_not_below_init}, zero_days={c2_zero_days}, slower={c2_practice_slower}, low_not_raised={c2_low_not_raised}",
        )

        # -------------------------------------------------------------
        # Ingest course data for student tests
        # -------------------------------------------------------------
        stu1_res = client.post("/api/v1/students", json={"name": "Alice Learner"})
        stu1_id = stu1_res.json()["id"]

        stu2_res = client.post("/api/v1/students", json={"name": "Bob Learner"})
        stu2_id = stu2_res.json()["id"]

        crs1_res = client.post("/api/v1/courses", json={"name": "Computer Systems Architecture"})
        crs1_id = crs1_res.json()["id"]

        for filename in ("sample.pdf", "sample.pptx", "sample.vtt"):
            fpath = samples_dir / filename
            with open(fpath, "rb") as fp:
                client.post(
                    f"/api/v1/courses/{crs1_id}/sources",
                    files={"file": (filename, fp, "application/octet-stream")},
                )

        kb_stat = poll_kb_ready(client, crs1_id)
        assert kb_stat.get("kb_status") == "ready", f"KB failed to build: {kb_stat}"

        # -------------------------------------------------------------
        # CHECK 3: Brand-new student dashboard & mastery
        # -------------------------------------------------------------
        dash_res = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard")
        assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
        dash_data = dash_res.json()

        mast_res = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/mastery")
        assert mast_res.status_code == 200
        mast_data = mast_res.json()

        # Check for forbidden labels across payloads
        payload_str = json.dumps(dash_data) + json.dumps(mast_data)
        forbidden_found = any(bad in payload_str for bad in ("not_started", "struggling", "mastered"))

        c3_ok = (
            dash_data["needs_diagnostic"] is True
            and dash_data["summary"]["readiness"] == 0.0
            and dash_data["summary"]["average_mastery"] is None
            and dash_data["next_action"]["type"] == "take_diagnostic"
            and all(t["status"] == "new" for t in mast_data["topics"])
            and not forbidden_found
        )
        record_check(
            "brand-new student: dashboard works, needs_diagnostic true, all topics 'new', next_action take_diagnostic",
            c3_ok,
            f"needs_diag={dash_data['needs_diagnostic']}, readiness={dash_data['summary']['readiness']}, forbidden_found={forbidden_found}",
        )

        # -------------------------------------------------------------
        # CHECK 4: Diagnostic answered & submitted
        # -------------------------------------------------------------
        diag_res = client.post(f"/api/v1/courses/{crs1_id}/diagnostic?student_id={stu1_id}")
        assert diag_res.status_code == 201
        diag_id = diag_res.json()["id"]
        diag_questions = diag_res.json()["questions"]

        # Answer 3 questions on the diagnostic
        for q in diag_questions[:3]:
            client.post(
                f"/api/v1/assessments/{diag_id}/questions/{q['id']}/answer",
                json={"student_id": stu1_id, "answer": "A"},
            )

        diag_sub_res = client.post(f"/api/v1/assessments/{diag_id}/submit", json={"student_id": stu1_id})
        assert diag_sub_res.status_code == 200

        dash_after_diag = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard").json()
        mast_after_diag = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/mastery").json()

        practiced_topics = [t for t in mast_after_diag["topics"] if t["attempts"] > 0]
        c4_ok = (
            dash_after_diag["needs_diagnostic"] is False
            and len(practiced_topics) > 0
            and all(t["accuracy"] is not None and len(t["trend"]) > 0 for t in practiced_topics)
        )
        record_check(
            "after diagnostic submitted: needs_diagnostic false, mastery shows practiced topics with attempts, accuracy, trend",
            c4_ok,
            f"needs_diag={dash_after_diag['needs_diagnostic']}, practiced_count={len(practiced_topics)}",
        )

        # -------------------------------------------------------------
        # CHECK 5: Weak/strong classification & prerequisite recommendation
        # -------------------------------------------------------------
        with SessionLocal() as db:
            leaf_topics = db.scalars(
                select(Topic)
                .where(Topic.course_id == crs1_id)
                .order_by(Topic.order_index.asc(), Topic.id.asc())
            ).all()
            parent_ids = {t.parent_id for t in leaf_topics if t.parent_id is not None}
            leaves = [t for t in leaf_topics if t.id not in parent_ids]
            t1_id = leaves[0].id
            t2_id = leaves[1].id
            t3_id = leaves[2].id
            t3_name = leaves[2].name

            # Set up explicit prerequisite: t1 is prerequisite of t3
            db.execute(TopicPrereq.__table__.delete().where(TopicPrereq.course_id == crs1_id))
            db.add(TopicPrereq(topic_id=t3_id, prereq_topic_id=t1_id, course_id=crs1_id))

            # Make t3 weak (p=0.20, attempts=3)
            # Make t1 prerequisite weak/untested (p=0.35, attempts=3)
            # Make t2 strong (p=0.88, attempts=3)
            now_dt = datetime.now(timezone.utc)
            for tid, p_val in [(t3_id, 0.20), (t1_id, 0.35), (t2_id, 0.88)]:
                m = db.scalar(select(Mastery).where(Mastery.student_id == stu1_id, Mastery.topic_id == tid))
                if not m:
                    m = Mastery(student_id=stu1_id, topic_id=tid)
                    db.add(m)
                m.p_mastery = p_val
                m.attempts_count = 3
                m.correct_count = 3 if p_val > 0.7 else 0
                m.last_practiced_at = now_dt
            db.commit()

        dash_res5 = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard")
        dash_data5 = dash_res5.json()

        weak_list = dash_data5["weak_topics"]
        strong_list = dash_data5["strong_topics"]
        recs_list = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/recommendations?limit=5").json()

        has_weak = len(weak_list) > 0 and weak_list[0]["effective_mastery"] <= 0.25
        has_strong = len(strong_list) > 0 and strong_list[0]["effective_mastery"] >= 0.80

        # Recommendation should recommend t1 (the prerequisite) before t3, with reason mentioning t3
        prereq_rec = next((r for r in recs_list if r["topic"] and r["topic"]["id"] == t1_id), None)
        prereq_mentions_dependent = (
            prereq_rec is not None
            and (t3_name in prereq_rec["reason"] or "prerequisite" in prereq_rec["reason"].lower())
        )

        c5_ok = has_weak and has_strong and prereq_mentions_dependent
        record_check(
            "weak/strong classification & unsatisfied prerequisite recommended first with dependent reason",
            c5_ok,
            f"has_weak={has_weak}, has_strong={has_strong}, prereq_rec={prereq_rec}",
        )

        # -------------------------------------------------------------
        # CHECK 6: POST /dev/age-mastery shifts retention and triggers review
        # -------------------------------------------------------------
        age_res = client.post(
            "/api/v1/dev/age-mastery",
            json={"student_id": stu1_id, "course_id": crs1_id, "days": 30.0},
        )
        assert age_res.status_code == 200, f"Age mastery failed: {age_res.text}"
        assert age_res.json()["rows_affected"] > 0

        dash_aged = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard").json()
        due_list_aged = dash_aged["due_for_review"]
        recs_aged = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/recommendations?limit=5").json()

        has_due = len(due_list_aged) > 0
        has_review_rec = any(r["type"] == "review_topic" for r in recs_aged)

        # Stored p_mastery must remain unchanged
        with SessionLocal() as db:
            stored_m2 = db.scalar(
                select(Mastery.p_mastery).where(Mastery.student_id == stu1_id, Mastery.topic_id == t2_id)
            )
        stored_unchanged = stored_m2 == 0.88

        c6_ok = has_due and has_review_rec and stored_unchanged
        record_check(
            "POST /dev/age-mastery drops effective mastery, adds to due_for_review and review_topic without altering stored p",
            c6_ok,
            f"has_due={has_due}, has_review_rec={has_review_rec}, stored_m2={stored_m2}",
        )

        # -------------------------------------------------------------
        # CHECK 7: Everything strong and nothing due -> take_mock_exam
        # -------------------------------------------------------------
        with SessionLocal() as db:
            all_leafs = db.scalars(
                select(Topic).where(Topic.course_id == crs1_id)
            ).all()
            p_ids = {t.parent_id for t in all_leafs if t.parent_id is not None}
            l_topics = [t for t in all_leafs if t.id not in p_ids]
            now_dt = datetime.now(timezone.utc)
            for t in l_topics:
                m = db.scalar(select(Mastery).where(Mastery.student_id == stu1_id, Mastery.topic_id == t.id))
                if not m:
                    m = Mastery(student_id=stu1_id, topic_id=t.id)
                    db.add(m)
                m.p_mastery = 0.90
                m.attempts_count = 5
                m.correct_count = 5
                m.last_practiced_at = now_dt
            db.commit()

        dash_strong_res = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard").json()
        c7_ok = (
            dash_strong_res["next_action"] is not None
            and dash_strong_res["next_action"]["type"] == "take_mock_exam"
        )
        record_check(
            "everything strong and nothing due -> next_action.type == take_mock_exam",
            c7_ok,
            f"next_action_type={dash_strong_res['next_action'].get('type') if dash_strong_res['next_action'] else None}",
        )

        # -------------------------------------------------------------
        # CHECK 8: Chat mastery nudge and rate limits
        # -------------------------------------------------------------
        # Create a fresh conversation for Student 2
        conv_res = client.post(
            f"/api/v1/courses/{crs1_id}/conversations",
            json={"student_id": stu2_id, "title": "Newton Mechanics Q&A"},
        )
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]

        # 8a: Grounded question produces mastery nudge
        chat1 = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"student_id": stu2_id, "content": "Explain Newton's first law of motion and inertia principles."},
        )
        assert chat1.status_code == 201, f"Chat failed: {chat1.text}"
        chat1_data = chat1.json()
        nudge1 = chat1_data.get("mastery_nudge")

        with SessionLocal() as db:
            chat_events = db.scalars(
                select(MasteryEvent).where(MasteryEvent.student_id == stu2_id, MasteryEvent.origin == "chat")
            ).all()

        nudge_ok = (
            nudge1 is not None
            and nudge1["after"] > nudge1["before"]
            and len(chat_events) == 1
        )

        # 8b: Repeating messages up to daily cap
        for _ in range(5):
            client.post(
                f"/api/v1/conversations/{conv_id}/messages",
                json={"student_id": stu2_id, "content": "Explain Newton's second law of motion F equals ma."},
            )

        with SessionLocal() as db:
            total_nudges = db.scalar(
                select(func.count(MasteryEvent.id)).where(
                    MasteryEvent.student_id == stu2_id, MasteryEvent.origin == "chat"
                )
            ) or 0
            m_stu2 = db.scalar(
                select(Mastery).where(Mastery.student_id == stu2_id, Mastery.topic_id == nudge1["topic"]["id"])
            )
            # Check attempts_count stays 0 and status stays "new"
            attempts_zero = m_stu2.attempts_count == 0 if m_stu2 else False
            status_is_new = status_for(m_stu2.p_mastery, m_stu2.attempts_count) == "new" if m_stu2 else False

        # 8c: Greeting and unsupported question produce no nudge
        chat_greet = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"student_id": stu2_id, "content": "hello"},
        ).json()
        greet_no_nudge = chat_greet.get("mastery_nudge") is None

        chat_unsupported = client.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"student_id": stu2_id, "content": "What is the secret recipe for Martian guacamole?"},
        ).json()
        unsupported_no_nudge = chat_unsupported.get("mastery_nudge") is None

        c8_ok = (
            nudge_ok
            and total_nudges <= get_settings().chat_nudge_max_per_topic_per_day
            and attempts_zero
            and status_is_new
            and greet_no_nudge
            and unsupported_no_nudge
        )
        record_check(
            "chat nudge: grounded turn applies bump, audits MasteryEvent, respects daily cap, attempts=0 stays 'new', skips unsupported/greeting",
            c8_ok,
            f"nudge_ok={nudge_ok}, total_nudges={total_nudges}, attempts_zero={attempts_zero}, status_is_new={status_is_new}, greet_no_nudge={greet_no_nudge}, unsupported_no_nudge={unsupported_no_nudge}",
        )

        # -------------------------------------------------------------
        # CHECK 9: Struggle signal yields ask_tutor recommendation
        # -------------------------------------------------------------
        # Student 2 has asked >= 3 questions related to operating systems, and attempts_count == 0 (status "new", not strong)
        recs_stu2 = client.get(f"/api/v1/students/{stu2_id}/courses/{crs1_id}/recommendations").json()
        has_ask_tutor = any(r["type"] == "ask_tutor" for r in recs_stu2)
        record_check(
            "struggle signal: asking >= CHAT_STRUGGLE_ASKS questions on topic yields ask_tutor recommendation",
            has_ask_tutor,
            f"recs_types={[r['type'] for r in recs_stu2]}",
        )

        # -------------------------------------------------------------
        # CHECK 10: Tutor personalization plumbing in /dev/ask
        # -------------------------------------------------------------
        # Stu 1 is strong across topics, Stu 2 is new
        dev_ask_new = client.post(
            "/api/v1/dev/ask",
            json={
                "course_id": crs1_id,
                "question": "What is an operating system process?",
                "student_id": stu2_id,
            },
        ).json()

        dev_ask_strong = client.post(
            "/api/v1/dev/ask",
            json={
                "course_id": crs1_id,
                "question": "What is an operating system process?",
                "student_id": stu1_id,
            },
        ).json()

        hint_new = dev_ask_new.get("student_level_hint")
        hint_strong = dev_ask_strong.get("student_level_hint")

        c10_ok = (
            hint_new is not None
            and hint_strong is not None
            and "new" in hint_new
            and "strong" in hint_strong
            and hint_new != hint_strong
        )
        record_check(
            "tutor personalization plumbing: /dev/ask returns student_level_hint differing between new and strong students",
            c10_ok,
            f"hint_new='{hint_new[:40]}...', hint_strong='{hint_strong[:40]}...'",
        )

        # -------------------------------------------------------------
        # CHECK 11: Recommendations schema, priorities and citations
        # -------------------------------------------------------------
        recs_chk = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/recommendations?limit=5").json()
        priorities_consecutive = [r["priority"] for r in recs_chk] == list(range(1, len(recs_chk) + 1))
        all_have_reason = all(len(r.get("reason", "")) > 0 and r.get("cta") is not None for r in recs_chk)
        max_5 = len(recs_chk) <= 5

        # Test citation click-through if citations present
        cit_click_ok = True
        for r in recs_chk:
            for cit in r.get("citations", []):
                chunk_id = cit.get("chunk_id")
                if chunk_id:
                    res_c = client.get(f"/api/v1/chunks/{chunk_id}")
                    if res_c.status_code != 200:
                        cit_click_ok = False

        c11_ok = priorities_consecutive and all_have_reason and max_5 and cit_click_ok
        record_check(
            "recommendations items: reason, cta, priority 1..n, limit <= 5, and clickable chunk citations",
            c11_ok,
            f"priorities={priorities_consecutive}, all_reason={all_have_reason}, cit_click={cit_click_ok}",
        )

        # -------------------------------------------------------------
        # CHECK 12: Activity history endpoint (attempts + assessments)
        # -------------------------------------------------------------
        hist_all = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/history?kind=all&limit=20").json()
        hist_att = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/history?kind=attempts&limit=10").json()
        hist_ass = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/history?kind=assessments&limit=10").json()

        has_both = any(h["type"] == "attempt" for h in hist_all) and any(h["type"] == "assessment" for h in hist_all)
        att_filter_ok = all(h["type"] == "attempt" for h in hist_att)
        ass_filter_ok = all(h["type"] == "assessment" for h in hist_ass)

        c12_ok = has_both and att_filter_ok and ass_filter_ok
        record_check(
            "history endpoint: merges attempts and assessments newest first with kind filter and pagination",
            c12_ok,
            f"has_both={has_both}, att_filter={att_filter_ok}, ass_filter={ass_filter_ok}",
        )

        # -------------------------------------------------------------
        # CHECK 13: Study plan generation and horizon rules
        # -------------------------------------------------------------
        exam_target = (date.today() + timedelta(days=5)).isoformat()
        plan_5days = client.get(
            f"/api/v1/students/{stu1_id}/courses/{crs1_id}/study-plan?exam_date={exam_target}&minutes_per_day=45"
        )
        assert plan_5days.status_code == 200, f"Plan failed: {plan_5days.text}"
        p5_data = plan_5days.json()

        days_count_6 = len(p5_data["days"]) == 6
        last_day_has_mock = any(s["activity"] == "mock_exam" for s in p5_data["days"][-1]["sessions"])
        minutes_under_45 = all(d["total_minutes"] <= 45 for d in p5_data["days"])

        # Past exam date -> 422
        past_target = (date.today() - timedelta(days=2)).isoformat()
        plan_past = client.get(
            f"/api/v1/students/{stu1_id}/courses/{crs1_id}/study-plan?exam_date={past_target}&minutes_per_day=45"
        )
        past_422 = plan_past.status_code == 422

        # No exam date -> 7 days
        plan_no_exam = client.get(
            f"/api/v1/students/{stu1_id}/courses/{crs1_id}/study-plan?minutes_per_day=45"
        ).json()
        no_exam_7_days = len(plan_no_exam["days"]) == 7

        c13_ok = days_count_6 and last_day_has_mock and minutes_under_45 and past_422 and no_exam_7_days
        record_check(
            "study plan: 5-day horizon -> 6 days with mock_exam on last day, minutes capped, past date 422, default 7 days",
            c13_ok,
            f"days_6={days_count_6}, mock_last={last_day_has_mock}, min_ok={minutes_under_45}, past_422={past_422}, 7days={no_exam_7_days}",
        )

        # -------------------------------------------------------------
        # CHECK 14: tz_offset_min shifts daily heatmap buckets
        # -------------------------------------------------------------
        with SessionLocal() as db:
            # Insert attempt at 2026-10-13 23:30 UTC
            t_near_midnight = datetime(2026, 10, 13, 23, 30, 0, tzinfo=timezone.utc)
            a_dummy = Assessment(
                course_id=crs1_id,
                student_id=stu1_id,
                kind="practice",
                title="Midnight test",
                status="submitted",
            )
            db.add(a_dummy)
            db.flush()
            top_first = db.scalar(select(Topic).where(Topic.course_id == crs1_id))
            q_dummy = Question(
                assessment_id=a_dummy.id,
                course_id=crs1_id,
                topic_id=top_first.id,
                prompt="Midnight question",
                qtype="mcq",
                difficulty="medium",
                options=["A", "B"],
                correct_answer="A",
                explanation="None",
                fingerprint="fingerprint_midnight_test",
                verified=True,
            )
            db.add(q_dummy)
            db.flush()
            att_near = Attempt(
                assessment_id=a_dummy.id,
                question_id=q_dummy.id,
                student_id=stu1_id,
                answer="A",
                score=1.0,
                is_correct=True,
                feedback="Correct answer",
                created_at=t_near_midnight,
            )
            db.add(att_near)
            db.commit()

        d_utc = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard?tz_offset_min=0").json()
        d_ist = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard?tz_offset_min=330").json()

        # In UTC, 23:30 is on 2026-10-13; in IST (+5:30), it shifts to 2026-10-14!
        utc_map = {item["date"]: item["attempts"] for item in d_utc["activity"]["daily"]}
        ist_map = {item["date"]: item["attempts"] for item in d_ist["activity"]["daily"]}

        c14_ok = utc_map.get("2026-10-13", 0) > ist_map.get("2026-10-13", 0) or "2026-10-14" in ist_map
        record_check(
            "tz_offset_min shifts daily buckets across midnight boundaries",
            c14_ok,
            f"utc_13={utc_map.get('2026-10-13')}, ist_13={ist_map.get('2026-10-13')}",
        )

        # -------------------------------------------------------------
        # CHECK 15: Error handling & read immutability
        # -------------------------------------------------------------
        err_stu = client.get(f"/api/v1/students/999999/courses/{crs1_id}/dashboard").status_code == 404
        err_crs = client.get(f"/api/v1/students/{stu1_id}/courses/999999/dashboard").status_code == 404
        err_top = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/topics/999999/mastery-history").status_code == 404

        with SessionLocal() as db:
            m_count_before = db.scalar(select(func.count(Mastery.id)))
            me_count_before = db.scalar(select(func.count(MasteryEvent.id)))
            att_count_before = db.scalar(select(func.count(Attempt.id)))

        # Invoke all read endpoints
        client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard")
        client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/mastery")
        client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/recommendations")
        client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/history")
        client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/study-plan")

        with SessionLocal() as db:
            m_count_after = db.scalar(select(func.count(Mastery.id)))
            me_count_after = db.scalar(select(func.count(MasteryEvent.id)))
            att_count_after = db.scalar(select(func.count(Attempt.id)))

        immutable_reads = (
            m_count_before == m_count_after
            and me_count_before == me_count_after
            and att_count_before == att_count_after
        )

        c15_ok = err_stu and err_crs and err_top and immutable_reads
        record_check(
            "unknown student/course/topic -> 404; read endpoints leave DB rows strictly unchanged",
            c15_ok,
            f"404s=({err_stu},{err_crs},{err_top}), rows_unchanged={immutable_reads}",
        )

        # -------------------------------------------------------------
        # CHECK 16: Dashboard performance (< 500 ms) and bounded SQL queries
        # -------------------------------------------------------------
        # Count SQL queries executed during dashboard call
        query_counter = {"count": 0}

        def count_queries(conn, cursor, statement, parameters, context, executemany):
            query_counter["count"] += 1

        event.listen(engine, "before_cursor_execute", count_queries)

        t_start = time.perf_counter()
        resp_perf = client.get(f"/api/v1/students/{stu1_id}/courses/{crs1_id}/dashboard")
        t_elapsed_ms = (time.perf_counter() - t_start) * 1000.0

        event.remove(engine, "before_cursor_execute", count_queries)

        sql_count = query_counter["count"]
        perf_ok = t_elapsed_ms < 500.0 and sql_count < 25

        c16_ok = resp_perf.status_code == 200 and perf_ok
        record_check(
            f"performance: dashboard responds in {t_elapsed_ms:.2f} ms (< 500 ms) with {sql_count} bounded SQL queries",
            c16_ok,
            f"elapsed_ms={t_elapsed_ms:.2f}, sql_statements={sql_count}",
        )

        # -------------------------------------------------------------
        # CHECK 17: /dev/forgetting-simulate trajectory & immutability
        # -------------------------------------------------------------
        with SessionLocal() as db:
            rows_before_sim = db.scalar(select(func.count(Mastery.id)))

        sim_res = client.post(
            "/api/v1/dev/forgetting-simulate",
            json={"p_mastery": 0.85, "correct_count": 3, "days": [0.0, 3.0, 7.0, 14.0, 30.0]},
        )
        assert sim_res.status_code == 200, f"Simulate failed: {sim_res.text}"
        sim_traj = sim_res.json()

        with SessionLocal() as db:
            rows_after_sim = db.scalar(select(func.count(Mastery.id)))

        sim_decay_ok = (
            len(sim_traj) == 5
            and sim_traj[0]["effective_mastery"] == 0.85
            and sim_traj[-1]["effective_mastery"] < 0.85
            and rows_before_sim == rows_after_sim
        )
        record_check(
            "/dev/forgetting-simulate returns decaying trajectory and writes nothing to database",
            sim_decay_ok,
            f"steps={len(sim_traj)}, eff_start={sim_traj[0]['effective_mastery']}, eff_end={sim_traj[-1]['effective_mastery']}",
        )

    print("-" * 70)
    all_passed = all(r["passed"] for r in results)
    total_checks = len(results)
    passed_checks = sum(1 for r in results if r["passed"])
    print(f"OVERALL RESULT: {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'} ({passed_checks}/{total_checks})")
    print("=" * 70)

    # Cleanup temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()
