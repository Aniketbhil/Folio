#!/usr/bin/env python3
"""Demo seed script for Folio backend.

Populates the database with a realistic scenario:
- Course: Introduction to Classical Mechanics (PHYS101)
- Ingested sample materials (PDF, PPTX, transcripts, text)
- Built Knowledge Base with topics and prerequisites
- Student 1: "Demo New Student" (empty state, diagnostic ready)
- Student 2: "Demo Active Student" (14-day history, mastered/in-progress/struggling/due topics,
  tutor conversations with flagged query, graded assessments)
"""

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import httpx
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.main import app
from app.models.assessment import Assessment, Attempt, Question
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.mastery import Mastery, MasteryEvent
from app.models.source import Chunk, Source
from app.models.student import Student
from app.models.topic import Topic


class DemoClient:
    """Wrapper that communicates via HTTP or in-process TestClient with token authentication."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._http_client: Optional[httpx.Client] = None
        self._test_client: Optional[Any] = None
        self.token: Optional[str] = None

        # Check if HTTP server is alive
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=1.5)
            if r.status_code == 200:
                self._http_client = httpx.Client(base_url=self.base_url, timeout=60.0)
                print(f"[Seed] Connected to running Folio server at {self.base_url}")
        except Exception:
            pass

        if self._http_client is None:
            from fastapi.testclient import TestClient
            self._test_client = TestClient(app)
            self._test_client.__enter__()
            print("[Seed] Folio server not reachable via HTTP; using in-process TestClient.")

    def set_token(self, token: Optional[str]) -> None:
        self.token = token

    def _prepare_kwargs(self, kwargs: dict) -> dict:
        if self.token:
            headers = dict(kwargs.get("headers") or {})
            if "Authorization" not in headers and "authorization" not in headers:
                headers["Authorization"] = f"Bearer {self.token}"
            kwargs["headers"] = headers
        return kwargs

    def get(self, url: str, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        if self._http_client:
            return self._http_client.get(url, **kwargs)
        return self._test_client.get(url, **kwargs)

    def post(self, url: str, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        if self._http_client:
            return self._http_client.post(url, **kwargs)
        return self._test_client.post(url, **kwargs)

    def delete(self, url: str, **kwargs):
        kwargs = self._prepare_kwargs(kwargs)
        if self._http_client:
            return self._http_client.delete(url, **kwargs)
        return self._test_client.delete(url, **kwargs)


def get_or_create_student(
    client: DemoClient,
    name: str,
    email: str,
    password: str = "Demo@1234",
) -> Tuple[int, Optional[str]]:
    """Create a student via signup or log in if existing, returning (student_id, access_token)."""
    # Try signing up
    r = client.post("/api/v1/auth/signup", json={"name": name, "email": email, "password": password})
    if r.status_code == 201:
        data = r.json()
        return data["student"]["id"], data.get("access_token")
    if r.status_code == 409:
        # Email already registered; log in
        r_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        if r_login.status_code == 200:
            data = r_login.json()
            return data["student"]["id"], data.get("access_token")
    # Fallback for servers running with AUTH_REQUIRED=false or dev endpoints
    r_fallback = client.post("/api/v1/students", json={"name": name})
    if r_fallback.status_code == 201:
        return r_fallback.json()["id"], None
    raise RuntimeError(f"Could not create student {name} ({email}): status {r.status_code} - {r.text}")


def seed_demo(base_url: str, material_dir_path: str, reset: bool) -> None:
    client = DemoClient(base_url)
    material_dir = Path(material_dir_path)

    DEMO_COURSE_NAME = "Introduction to Classical Mechanics (PHYS101 - Fall 2026)"
    STUDENT_NEW_NAME = "Demo New Student"
    STUDENT_NEW_EMAIL = "demo.new@folio.demo"
    STUDENT_ACTIVE_NAME = "Demo Active Student"
    STUDENT_ACTIVE_EMAIL = "demo.active@folio.demo"

    # 1. Reset logic if requested
    if reset:
        print("[Seed] Reset requested. Clearing previous demo entities...")
        with SessionLocal() as db:
            c = db.scalar(select(Course).where(Course.name == DEMO_COURSE_NAME))
            if c:
                db.delete(c)
            for semail in [STUDENT_NEW_EMAIL, STUDENT_ACTIVE_EMAIL]:
                s = db.scalar(select(Student).where(func.lower(Student.email) == semail.lower()))
                if s:
                    db.delete(s)
            for sname in [STUDENT_NEW_NAME, STUDENT_ACTIVE_NAME, "Demo New Student (new@folio.demo)", "Demo Active Student (active@folio.demo)"]:
                s = db.scalar(select(Student).where(Student.name == sname))
                if s:
                    db.delete(s)
            db.commit()
        print("[Seed] Reset completed.")

    # 2. Check idempotency
    with SessionLocal() as db:
        existing_course = db.scalar(select(Course).where(Course.name == DEMO_COURSE_NAME))
        existing_active_student = db.scalar(
            select(Student).where(
                (Student.name == STUDENT_ACTIVE_NAME) | (func.lower(Student.email) == STUDENT_ACTIVE_EMAIL.lower())
            )
        )
        if existing_course and existing_active_student and not reset:
            print(f"[Seed] Demo course already exists (ID: {existing_course.id}).")
            print(f"[Seed] Active student already exists (ID: {existing_active_student.id}).")
            print("[Seed] Use --reset to re-seed demo data from scratch.")
            _print_summary(existing_course.id, existing_active_student.id, base_url)
            return

    # 3. Create or authenticate demo students
    print("[Seed] Authenticating demo students...")
    s2_id, s2_token = get_or_create_student(client, STUDENT_ACTIVE_NAME, STUDENT_ACTIVE_EMAIL)
    s1_id, s1_token = get_or_create_student(client, STUDENT_NEW_NAME, STUDENT_NEW_EMAIL)
    print(f"[Seed] Demo Active Student ID: {s2_id}")
    print(f"[Seed] Demo New Student ID: {s1_id}")

    # Set active student token for subsequent course and content creation
    client.set_token(s2_token)

    # 4. Create Demo Course
    print("[Seed] Creating demo course 'Introduction to Classical Mechanics' (PHYS101)...")
    res = client.post(
        "/api/v1/courses",
        json={
            "name": DEMO_COURSE_NAME,
            "description": "Foundational classical physics covering Newton's laws, dynamics, and motion.",
        },
    )
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create course: {res.text}")
    course_data = res.json()
    course_id = course_data["id"]
    print(f"[Seed] Course created with ID: {course_id}")

    # 5. Upload sample materials
    sample_files = [
        "sample.pdf",
        "sample.pptx",
        "sample.vtt",
        "sample.srt",
        "sample_youtube.json",
        "sample_plain.txt",
        "sample_timestamped.txt",
    ]

    uploaded_sources = []
    for fname in sample_files:
        fpath = material_dir / fname
        if not fpath.exists():
            print(f"[Seed] Warning: {fpath} does not exist, skipping.")
            continue

        print(f"[Seed] Uploading {fname}...")
        with open(fpath, "rb") as f:
            mime = "application/octet-stream"
            if fname.endswith(".pdf"):
                mime = "application/pdf"
            elif fname.endswith(".pptx"):
                mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            elif fname.endswith(".json"):
                mime = "application/json"
            elif fname.endswith(".vtt") or fname.endswith(".srt") or fname.endswith(".txt"):
                mime = "text/plain"

            upload_res = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": (fname, f.read(), mime)},
            )
            if upload_res.status_code in (200, 201, 202):
                src_info = upload_res.json()
                uploaded_sources.append(src_info["id"])
            else:
                print(f"[Seed] Failed to upload {fname}: {upload_res.text}")

    # Poll until all sources are ready
    print(f"[Seed] Waiting for {len(uploaded_sources)} sources to complete ingestion...")
    start_time = time.time()
    while time.time() - start_time < 45:
        all_ready = True
        for src_id in uploaded_sources:
            status_res = client.get(f"/api/v1/sources/{src_id}")
            if status_res.status_code == 200:
                st = status_res.json().get("status")
                if st in ("processing", "queued"):
                    all_ready = False
                    break
        if all_ready:
            break
        time.sleep(1.0)
    print("[Seed] Sources ingested successfully.")

    # 5. Build Knowledge Base
    print("[Seed] Triggering Knowledge Base build...")
    kb_trigger = client.post(f"/api/v1/courses/{course_id}/kb/rebuild")
    if kb_trigger.status_code not in (200, 202):
        print(f"[Seed] KB build trigger returned: {kb_trigger.text}")

    # Wait for KB build to finish
    print("[Seed] Polling KB status...")
    start_time = time.time()
    while time.time() - start_time < 60:
        kb_res = client.get(f"/api/v1/courses/{course_id}/kb/status")
        if kb_res.status_code == 200:
            kb_data = kb_res.json()
            if kb_data.get("kb_status") == "ready":
                print(f"[Seed] KB built with status ready.")
                break
            elif kb_data.get("kb_status") == "failed":
                print(f"[Seed] KB build failed: {kb_data.get('kb_error')}")
                break
        time.sleep(1.0)

    # 6. Seed 10-14 days of realistic activity for Student 2
    print("[Seed] Generating realistic 14-day history for Student 2...")
    with SessionLocal() as db:
        topics = list(db.scalars(select(Topic).where(Topic.course_id == course_id)).all())
        now = datetime.now(timezone.utc)

        # Distribute topics across states
        # masteries: 4-5 mastered, 2-3 in-progress, 1-2 struggling, 1 due for review
        # If fewer topics generated, we ensure coverage by cycling or synthesizing topics
        if len(topics) < 8:
            # Create extra topics if needed to showcase full dashboard richness
            extra_titles = [
                "Conservation of Momentum",
                "Friction and Surface Resistance",
                "Centripetal Acceleration and Circular Motion",
                "Work, Energy, and Power",
            ]
            for extra in extra_titles:
                et = Topic(
                    course_id=course_id,
                    title=extra,
                    description=f"Core dynamics module on {extra.lower()}.",
                )
                db.add(et)
            db.commit()
            topics = list(db.scalars(select(Topic).where(Topic.course_id == course_id)).all())

        # Category 1: 4 Mastered topics (p >= 0.85, 3-5 correct attempts spread over last 12 days)
        mastered_topics = topics[:4]
        for idx, t in enumerate(mastered_topics):
            p = 0.88 + (idx * 0.03)
            last_practiced = now - timedelta(days=2 + idx)
            m = Mastery(
                student_id=s2_id,
                topic_id=t.id,
                p_mastery=min(p, 0.98),
                attempts_count=4 + idx,
                correct_count=4 + idx,
                last_practiced_at=last_practiced,
                updated_at=last_practiced,
            )
            db.add(m)
            # Add mastery events backdated
            for d in range(3):
                ev_time = last_practiced - timedelta(days=d * 2)
                ev = MasteryEvent(
                    student_id=s2_id,
                    topic_id=t.id,
                    origin="quiz",
                    p_before=0.4 + (d * 0.15),
                    p_after=0.55 + (d * 0.15),
                    created_at=ev_time,
                )
                db.add(ev)

        # Category 2: 2 In-Progress topics (p between 0.4 and 0.7)
        in_progress_topics = topics[4:6]
        for idx, t in enumerate(in_progress_topics):
            last_practiced = now - timedelta(days=1 + idx)
            m = Mastery(
                student_id=s2_id,
                topic_id=t.id,
                p_mastery=0.52 + (idx * 0.1),
                attempts_count=2,
                correct_count=1,
                last_practiced_at=last_practiced,
                updated_at=last_practiced,
            )
            db.add(m)
            ev = MasteryEvent(
                student_id=s2_id,
                topic_id=t.id,
                origin="quiz",
                p_before=0.3,
                p_after=0.52 + (idx * 0.1),
                created_at=last_practiced,
            )
            db.add(ev)

        # Category 3: 1 Struggling topic (p < 0.3, repeated incorrect attempts, detected misconception)
        struggling_topic = topics[6] if len(topics) > 6 else topics[0]
        struggling_time = now - timedelta(days=3)
        m_struggle = Mastery(
            student_id=s2_id,
            topic_id=struggling_topic.id,
            p_mastery=0.22,
            attempts_count=3,
            correct_count=0,
            last_practiced_at=struggling_time,
            updated_at=struggling_time,
        )
        db.add(m_struggle)
        ev_st = MasteryEvent(
            student_id=s2_id,
            topic_id=struggling_topic.id,
            origin="quiz",
            p_before=0.30,
            p_after=0.22,
            created_at=struggling_time,
        )
        db.add(ev_st)

        # Category 4: 1 Due for review topic (practiced 10 days ago, decayed)
        due_topic = topics[7] if len(topics) > 7 else topics[1]
        decayed_time = now - timedelta(days=10)
        m_due = Mastery(
            student_id=s2_id,
            topic_id=due_topic.id,
            p_mastery=0.90,
            attempts_count=3,
            correct_count=3,
            last_practiced_at=decayed_time,
            updated_at=decayed_time,
        )
        db.add(m_due)
        ev_due = MasteryEvent(
            student_id=s2_id,
            topic_id=due_topic.id,
            origin="quiz",
            p_before=0.75,
            p_after=0.90,
            created_at=decayed_time,
        )
        db.add(ev_due)

        # Create 3 Graded Assessments with Attempts
        chunks = list(db.scalars(select(Chunk).where(Chunk.course_id == course_id)).all())
        sample_chunk_ids = [c.id for c in chunks[:3]] if chunks else []

        for a_idx in range(3):
            ass_time = now - timedelta(days=3 * (3 - a_idx))
            assessment = Assessment(
                course_id=course_id,
                student_id=s2_id,
                title=f"Practice Module Quiz {a_idx + 1}",
                kind="quiz",
                status="submitted",
                score=1.0 if a_idx != 1 else 0.5,
                submitted_at=ass_time,
                created_at=ass_time - timedelta(minutes=15),
            )
            db.add(assessment)
            db.flush()

            for q_idx in range(2):
                topic_for_q = topics[(a_idx + q_idx) % len(topics)]
                is_correct = not (a_idx == 1 and q_idx == 0)  # Make 1 incorrect for realism
                misconception = "Equates velocity with net force" if not is_correct else None

                question = Question(
                    assessment_id=assessment.id,
                    course_id=course_id,
                    topic_id=topic_for_q.id,
                    qtype="mcq",
                    difficulty="medium",
                    prompt=f"According to Newton's laws, what happens when net external force is zero?",
                    options=["Object decelerates to rest", "Object maintains constant velocity", "Object accelerates", "Mass increases"],
                    correct_answer="Object maintains constant velocity",
                    explanation="Newton's First Law guarantees constant velocity in the absence of net force.",
                    source_chunk_ids=sample_chunk_ids,
                    verified=True,
                    fingerprint=f"demo_q_{a_idx}_{q_idx}_{topic_for_q.id}",
                    position=q_idx,
                    created_at=assessment.created_at,
                )
                db.add(question)
                db.flush()

                attempt = Attempt(
                    student_id=s2_id,
                    question_id=question.id,
                    assessment_id=assessment.id,
                    answer="Object maintains constant velocity" if is_correct else "Object decelerates to rest",
                    is_correct=is_correct,
                    score=1.0 if is_correct else 0.0,
                    feedback="Spot on! Newton's first law states inertia preserves motion." if is_correct else "Incorrect: an object without net force does not slow down unless friction is present.",
                    citations=[],
                    misconception=misconception,
                    time_taken_sec=24.5,
                    created_at=ass_time,
                )
                db.add(attempt)

        # Create 3 Tutor Conversations with 2-4 turns, including 1 flagged query
        # Conversation 1: Grounded discussion on Newton's First Law
        c1_time = now - timedelta(days=5)
        conv1 = Conversation(
            course_id=course_id,
            student_id=s2_id,
            title="Clarifying Inertia and Mass",
            created_at=c1_time,
        )
        db.add(conv1)
        db.flush()

        m1_1 = Message(
            conversation_id=conv1.id,
            role="user",
            content="Can you explain why mass is considered a measure of inertia?",
            created_at=c1_time,
        )
        m1_2 = Message(
            conversation_id=conv1.id,
            role="assistant",
            content="Mass quantifies an object's resistance to acceleration. The greater the mass, the smaller the acceleration produced by a given net force (F = ma) [1].",
            grounding_status="grounded",
            citations=[{"source_id": uploaded_sources[0] if uploaded_sources else 1, "page_number": 2, "section_title": "First Law"}],
            created_at=c1_time + timedelta(seconds=12),
        )
        m1_3 = Message(
            conversation_id=conv1.id,
            role="user",
            content="Does that mean in space where there is no gravity, inertia is still the same?",
            created_at=c1_time + timedelta(seconds=45),
        )
        m1_4 = Message(
            conversation_id=conv1.id,
            role="assistant",
            content="Exactly right! Mass and inertia are intrinsic properties independent of gravity or location [2].",
            grounding_status="grounded",
            citations=[{"source_id": uploaded_sources[0] if uploaded_sources else 1, "page_number": 2, "section_title": "First Law"}],
            created_at=c1_time + timedelta(seconds=60),
        )
        db.add_all([m1_1, m1_2, m1_3, m1_4])

        # Conversation 2: Flagged/refused off-topic query
        c2_time = now - timedelta(days=2)
        conv2 = Conversation(
            course_id=course_id,
            student_id=s2_id,
            title="Non-course question (flagged)",
            created_at=c2_time,
        )
        db.add(conv2)
        db.flush()

        m2_1 = Message(
            conversation_id=conv2.id,
            role="user",
            content="What is the best recipe for baking chocolate chip cookies?",
            created_at=c2_time,
        )
        m2_2 = Message(
            conversation_id=conv2.id,
            role="assistant",
            content="I am only able to answer questions directly grounded in the course materials for Introduction to Classical Mechanics. Please ask a physics-related question!",
            grounding_status="unsupported",
            meta={"flagged": True, "flag_reason": "unsupported"},
            citations=[],
            created_at=c2_time + timedelta(seconds=10),
        )
        db.add_all([m2_1, m2_2])

        # Conversation 3: Action & Reaction discussion
        c3_time = now - timedelta(days=1)
        conv3 = Conversation(
            course_id=course_id,
            student_id=s2_id,
            title="Newton's Third Law in Rocket Propulsion",
            created_at=c3_time,
        )
        db.add(conv3)
        db.flush()

        m3_1 = Message(
            conversation_id=conv3.id,
            role="user",
            content="How does a rocket push forward in a vacuum if there's no air to push against?",
            created_at=c3_time,
        )
        m3_2 = Message(
            conversation_id=conv3.id,
            role="assistant",
            content="A rocket exerts a downward force on the escaping exhaust gas; by Newton's Third Law, the gas exerts an equal and opposite forward reaction force on the rocket [1].",
            grounding_status="grounded",
            citations=[{"source_id": uploaded_sources[0] if uploaded_sources else 1, "page_number": 4, "section_title": "Third Law"}],
            created_at=c3_time + timedelta(seconds=15),
        )
        db.add_all([m3_1, m3_2])

        db.commit()

    print("[Seed] Student 2 activity history successfully backdated.")
    _print_summary(course_id, s2_id, base_url, s1_id)


def _print_summary(course_id: int, active_student_id: int, base_url: str, new_student_id: Optional[int] = None) -> None:
    with SessionLocal() as db:
        topics_count = db.query(Topic).filter(Topic.course_id == course_id).count()
        chunks_count = db.query(Chunk).filter(Chunk.course_id == course_id).count()
        convs = list(db.scalars(select(Conversation).where(Conversation.student_id == active_student_id)).all())

    print("\n" + "=" * 60)
    print("DEMO SEED COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print(f"Course ID:         {course_id} (PHYS101)")
    if new_student_id:
        print(f"New Student ID:    {new_student_id} (demo.new@folio.demo)")
    print(f"Active Student ID: {active_student_id} (demo.active@folio.demo)")
    print(f"Total Topics:      {topics_count}")
    print(f"Total Chunks:      {chunks_count}")
    print(f"Conversations:     {[c.id for c in convs]}")
    print("\nCredentials:")
    print("  - Demo New Student:    demo.new@folio.demo    / Demo@1234")
    print("  - Demo Active Student: demo.active@folio.demo / Demo@1234")
    print("\nTry testing live endpoints (login first to get TOKEN):")
    print(f"  TOKEN=$(curl -s -X POST {base_url}/api/v1/auth/login -H 'Content-Type: application/json' -d '{{\"email\":\"demo.active@folio.demo\",\"password\":\"Demo@1234\"}}' | jq -r .access_token)")
    print(f"1. New student dashboard:")
    if new_student_id:
        print(f"   curl -s {base_url}/api/v1/students/{new_student_id}/courses/{course_id}/dashboard -H \"Authorization: Bearer $TOKEN\" | jq .")
    print(f"2. Active student rich dashboard:")
    print(f"   curl -s {base_url}/api/v1/students/{active_student_id}/courses/{course_id}/dashboard -H \"Authorization: Bearer $TOKEN\" | jq .")
    print(f"3. Active student next recommended action:")
    print(f"   curl -s {base_url}/api/v1/students/{active_student_id}/courses/{course_id}/recommendations -H \"Authorization: Bearer $TOKEN\" | jq .")
    print(f"4. Active student study plan:")
    print(f"   curl -s \"{base_url}/api/v1/students/{active_student_id}/courses/{course_id}/study-plan?minutes_per_day=45\" -H \"Authorization: Bearer $TOKEN\" | jq .")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Folio demo course and students.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Folio backend base URL")
    parser.add_argument("--material-dir", default="./samples", help="Path to sample files directory")
    parser.add_argument("--reset", action="store_true", help="Clear previous demo course and students")
    args = parser.parse_args()

    seed_demo(args.base_url, args.material_dir, args.reset)
