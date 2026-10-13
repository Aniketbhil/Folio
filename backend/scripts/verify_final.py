#!/usr/bin/env python3
"""Comprehensive verification suite for Prompt 8 (Final hardening, eval harness, and seed)."""

import json
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import get_settings
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.assessment import Assessment, Attempt, Question
from app.models.conversation import Conversation, Message
from app.models.course import Course
from app.models.mastery import Mastery, MasteryEvent
from app.models.source import Chunk, Source
from app.models.student import Student
from app.models.topic import Topic
from app.services.ingestion.pipeline import get_active_ingestion_count
from app.services.kb.heuristic import STOPWORDS
from app.services.learner.forgetting import effective_mastery, stability_days


def test_part_0_fixes(client: TestClient) -> None:
    print("\n--- 1. Testing Part 0 Fixes ---")
    settings = get_settings()

    # A. Multiplicative stability
    c2_stab = stability_days(2)
    expected_c2 = min(settings.forget_max_days, settings.forget_base_days * (1.0 + settings.forget_per_correct * 2))
    assert abs(c2_stab - expected_c2) < 1e-4, f"Stability mismatch: {c2_stab} vs {expected_c2}"

    # B. Effective mastery clamp
    eff_low = effective_mastery(p_mastery=0.10, last_practiced_at=None, correct_count=0)
    assert eff_low == 0.10, f"Expected 0.10 un-decayed, got {eff_low}"

    # C. Pure forgetting simulate endpoint
    res = client.post(
        "/api/v1/dev/forgetting-simulate",
        json={"p_mastery": 0.90, "correct_count": 3, "days": [0, 5, 10, 30]},
    )
    assert res.status_code == 200, f"Simulate failed: {res.text}"
    sim_data = res.json()
    assert isinstance(sim_data, list), f"Expected list, got {sim_data}"
    assert len(sim_data) == 4
    assert "effective_mastery" in sim_data[0]

    # D. Stopwords check
    assert "what" in STOPWORDS and "how" in STOPWORDS and "why" in STOPWORDS, "Question words missing from stopwords"
    print("✓ Part 0 fixes verified.")


def test_middleware_and_headers(client: TestClient) -> None:
    print("\n--- 2. Testing Middleware and Headers ---")
    # A. Auto-generated X-Request-ID
    r1 = client.get("/api/v1/health")
    assert r1.status_code == 200
    assert "x-request-id" in r1.headers, "X-Request-ID header missing from response"

    # B. Echo custom X-Request-ID
    custom_id = "test-req-custom-12345"
    r2 = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert r2.status_code == 200
    assert r2.headers.get("x-request-id") == custom_id, f"Expected echo {custom_id}, got {r2.headers.get('x-request-id')}"
    print("✓ Request logging middleware and X-Request-ID verified.")


def test_sqlite_configuration() -> None:
    print("\n--- 3. Testing SQLite Pragmas ---")
    with engine.connect() as conn:
        res = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        assert res == 5000, f"Expected busy_timeout 5000, got {res}"
    print("✓ SQLite PRAGMA busy_timeout=5000 verified.")


def test_content_sniffing(client: TestClient) -> None:
    print("\n--- 4. Testing Magic Byte Content Sniffing ---")
    # Create temp course
    c_res = client.post("/api/v1/courses", json={"name": "Sniff Test Course"})
    assert c_res.status_code == 201
    course_id = c_res.json()["id"]

    # Disguised fake PDF (plain text claiming to be PDF)
    fake_pdf = b"Hello, this is definitely not a PDF file format."
    r_fake_pdf = client.post(
        f"/api/v1/courses/{course_id}/sources",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")},
    )
    assert r_fake_pdf.status_code == 415, f"Expected 415 unsupported_file_type, got {r_fake_pdf.status_code}: {r_fake_pdf.text}"
    err = r_fake_pdf.json().get("error", {})
    assert err.get("code") == "unsupported_file_type"

    # Disguised fake PPTX (plain text claiming to be PPTX)
    fake_pptx = b"This is not a zip or pptx file."
    r_fake_pptx = client.post(
        f"/api/v1/courses/{course_id}/sources",
        files={"file": ("fake.pptx", fake_pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
    )
    assert r_fake_pptx.status_code == 415
    print("✓ Magic byte sniffing properly rejects disguised uploads with 415.")


def test_pagination_bounds(client: TestClient) -> None:
    print("\n--- 5. Testing Pagination Query Bounds ---")
    # Find existing source
    with SessionLocal() as db:
        src = db.scalar(select(Source))
    if src:
        # Limit > 100
        r_over = client.get(f"/api/v1/sources/{src.id}/chunks?limit=105")
        assert r_over.status_code == 422, f"Expected 422 for limit>100, got {r_over.status_code}"
        # Offset < 0
        r_under = client.get(f"/api/v1/sources/{src.id}/chunks?offset=-1")
        assert r_under.status_code == 422, f"Expected 422 for offset<0, got {r_under.status_code}"
    print("✓ Pagination bounds strictly enforced (422 validation_error).")


def test_meta_and_health_endpoints(client: TestClient) -> None:
    print("\n--- 6. Testing /meta and /health Endpoints ---")
    # GET /api/v1/meta
    r_meta = client.get("/api/v1/meta")
    assert r_meta.status_code == 200
    meta_data = r_meta.json()
    assert "version" in meta_data
    assert "enums" in meta_data
    assert "thresholds" in meta_data
    assert "limits" in meta_data
    assert "features" in meta_data
    assert "image_captioning" in meta_data["features"]

    # GET /health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    h_data = r_health.json()
    assert "uptime_sec" in h_data
    assert "counts" in h_data
    assert "ingestion_active" in h_data
    print("✓ Meta and extended health check verified.")


def test_student_cascading_delete(client: TestClient) -> None:
    print("\n--- 7. Testing DELETE /students/{id} Cascading Delete ---")
    # Create student
    s_res = client.post("/api/v1/students", json={"name": "Cascade Test Student"})
    assert s_res.status_code == 201
    s_id = s_res.json()["id"]

    # Add mastery record directly
    with SessionLocal() as db:
        top = db.scalar(select(Topic))
        if not top:
            crs = Course(name="Temp Course For Delete")
            db.add(crs)
            db.flush()
            top = Topic(course_id=crs.id, title="Temp Topic")
            db.add(top)
            db.flush()
        m = Mastery(student_id=s_id, topic_id=top.id, p_mastery=0.75, attempts_count=2, correct_count=2)
        db.add(m)
        conv = Conversation(course_id=top.course_id, student_id=s_id, title="Test Conv")
        db.add(conv)
        db.commit()

    # Delete student
    del_res = client.delete(f"/api/v1/students/{s_id}")
    assert del_res.status_code == 200, f"Delete failed: {del_res.text}"
    assert del_res.json()["deleted"] is True

    # Verify cascades in DB
    with SessionLocal() as db:
        assert db.scalar(select(Student).where(Student.id == s_id)) is None
        assert db.query(Mastery).filter(Mastery.student_id == s_id).count() == 0
        assert db.query(Conversation).filter(Conversation.student_id == s_id).count() == 0
    print("✓ DELETE /students/{id} cascades cleanly to all related records.")


def test_dev_integrity_check(client: TestClient) -> None:
    print("\n--- 8. Testing /dev/integrity-check ---")
    r_check = client.get("/api/v1/dev/integrity-check?fix=false")
    assert r_check.status_code == 200, f"Integrity check failed: {r_check.text}"
    data = r_check.json()
    assert "clean" in data
    assert "issues" in data
    print(f"✓ Integrity check endpoint passed (Clean: {data['clean']}).")


def test_openapi_and_eval_artifacts() -> None:
    print("\n--- 9. Testing OpenAPI Export & Evaluation Artifacts ---")
    # Check openapi.json
    openapi_file = backend_dir / "openapi.json"
    assert openapi_file.exists(), f"openapi.json does not exist at {openapi_file}"
    with open(openapi_file, "r") as f:
        schema = json.load(f)
    assert "paths" in schema
    assert len(schema["paths"]) > 10

    # Check eval_results
    eval_dir = backend_dir / "eval_results"
    required_eval_files = [
        "summary.json",
        "summary.txt",
        "retrieval_threshold_sweep.csv",
        "retrieval_threshold_sweep.png",
        "tutor_flagged.json",
        "quiz_eval.csv",
        "personalization_trajectories.png",
        "personalization_efficiency.png",
    ]
    for ef in required_eval_files:
        p = eval_dir / ef
        assert p.exists(), f"Evaluation artifact {ef} missing from {eval_dir}"
    print("✓ OpenAPI schema and all evaluation artifacts verified on disk.")


def main() -> None:
    print("============================================================")
    print("FOLIO BACKEND FINAL VERIFICATION SUITE (PROMPT 8)")
    print("============================================================")
    client = TestClient(app)

    test_part_0_fixes(client)
    test_middleware_and_headers(client)
    test_sqlite_configuration()
    test_content_sniffing(client)
    test_pagination_bounds(client)
    test_meta_and_health_endpoints(client)
    test_student_cascading_delete(client)
    test_dev_integrity_check(client)
    test_openapi_and_eval_artifacts()

    print("\n============================================================")
    print("ALL FINAL VERIFICATION CHECKS PASSED (PROMPT 8 READY)")
    print("============================================================\n")


if __name__ == "__main__":
    main()
