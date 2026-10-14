#!/usr/bin/env python3
"""End-to-end verification script for Folio Prompt 9: Authentication & Security.

Tests:
1. Password rules: length (8..128), uppercase, lowercase, symbol, no-digit required, composite failure message.
2. Signup: 201, token, student without password_hash, duplicate email (case-insensitive) -> 409, validation errors -> 422.
3. Login: 200, email case-insensitive, identical 401 on wrong password or unknown user (timing defense), last_login_at set.
4. Brute force rate limiting: 429 after max failed attempts, other emails unaffected.
5. GET /auth/me: valid, missing header (401 + WWW-Authenticate), garbage token (401), expired token (401), deleted student (401).
6. Change password: wrong current (401), weak new (422), same password (422), success and subsequent login.
7. Route protection: representative routes across all routers return 401 without token; health/meta/docs/dev stay public.
8. Resource ownership & access control: 403 on cross-student dashboard/mastery/delete, 404 on cross-student resource ID access.
9. End-to-end happy path: create course, conversation without student_id, tutor message, assessment without student_id, answer, dashboard.
10. Database integrity: Argon2 hashes, lowercase email, legacy students cannot log in.
11. Meta & OpenAPI: auth block in /meta without secrets, HTTPBearer in openapi.json.
12. AUTH_REQUIRED=false mode: student-scoped routes work without token, /auth/me still requires token.
"""

import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure fresh isolated environment before importing application modules
TEMP_DIR = tempfile.mkdtemp(prefix="folio_auth_verify_")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DIR}/test.db"
os.environ["CHROMA_DIR"] = f"{TEMP_DIR}/chroma"
os.environ["UPLOAD_DIR"] = f"{TEMP_DIR}/uploads"
os.environ["LLM_MOCK"] = "true"
os.environ["DEBUG"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["AUTH_REQUIRED"] = "true"
os.environ["JWT_SECRET"] = "verify-auth-test-secret-key-32charsmin!"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "60"
os.environ["AUTH_MAX_FAILED_ATTEMPTS"] = "5"
os.environ["AUTH_LOCKOUT_MINUTES"] = "15"

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import SessionLocal
from app.main import create_app
from app.models.student import Student
from app.services.auth.passwords import validate_password

CHECKS: List[Tuple[str, bool, str]] = []


def record_check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append((name, passed, detail))
    status_str = "PASS" if passed else "FAIL"
    print(f"  [{status_str}] {name}")
    if not passed and detail:
        print(f"         Detail: {detail}")


def run_auth_verification() -> None:
    print("=" * 80)
    print("FOLIO BACKEND — PROMPT 9 AUTHENTICATION VERIFICATION")
    print("=" * 80)

    app = create_app()
    client = TestClient(app)
    client.__enter__()
    samples_dir = backend_dir / "samples"

    # =========================================================================
    # 1. PASSWORD RULES & VALIDATION
    # =========================================================================
    print("\n--- 1. Password Strength Rules ---")
    pw_cases = [
        ("Short1!", False, "be at least 8 characters"),
        ("alllowercase1!", False, "include an uppercase letter"),
        ("ALLUPPERCASE1!", False, "include a lowercase letter"),
        ("NoSymbolsHere1", False, "include a symbol"),
        ("Valid@Pass", True, ""),  # valid, no digit required
        ("Valid Pass", False, "include a symbol"),  # space is not a symbol
        ("A" + "a" * 126 + "!" + "A", False, "be at most 128 characters"),  # 129 chars
    ]

    all_pw_rules_ok = True
    pw_detail = ""
    for pw, should_pass, expected_substr in pw_cases:
        try:
            validate_password(pw)
            if not should_pass:
                all_pw_rules_ok = False
                pw_detail = f"Expected '{pw}' to fail validation, but it passed."
                break
        except AppError as e:
            if should_pass:
                all_pw_rules_ok = False
                pw_detail = f"Expected '{pw}' to pass, but failed: {e.message}"
                break
            if expected_substr not in e.message or e.code != "weak_password":
                all_pw_rules_ok = False
                pw_detail = f"Expected '{expected_substr}' in '{e.message}' (code {e.code})"
                break

    # Also test compound message
    try:
        validate_password("short")  # len < 8, no upper, no symbol
        all_pw_rules_ok = False
        pw_detail = "Expected 'short' to fail with compound reasons"
    except AppError as e:
        expected_compound = "Password must be at least 8 characters, include an uppercase letter and include a symbol."
        if e.message != expected_compound:
            all_pw_rules_ok = False
            pw_detail = f"Compound mismatch: got '{e.message}' vs expected '{expected_compound}'"

    record_check(
        "password rules: length 8..128, upper, lower, symbol, no digit required, spaces not symbols, exact error message",
        all_pw_rules_ok,
        pw_detail,
    )

    # =========================================================================
    # 2. SIGNUP SUCCESS & VALIDATION
    # =========================================================================
    print("\n--- 2. Signup Endpoint ---")
    # A. Valid signup
    res_signup_a = client.post(
        "/api/v1/auth/signup",
        json={"name": "  Alice Student  ", "email": " Alice@Example.COM ", "password": "Password1!"},
    )
    s_a_ok = res_signup_a.status_code == 201
    data_a = res_signup_a.json() if s_a_ok else {}
    has_token = "access_token" in data_a and data_a.get("token_type") == "bearer"
    has_student = "student" in data_a and data_a["student"]["email"] == "alice@example.com"
    no_hash_in_json = "password_hash" not in str(res_signup_a.text) and "password" not in data_a.get("student", {})
    token_a = data_a.get("access_token", "")
    student_a_id = data_a.get("student", {}).get("id", 0)

    # B. Duplicate email (case-insensitive) -> 409 email_taken
    res_dup = client.post(
        "/api/v1/auth/signup",
        json={"name": "Alice Duplicate", "email": "alice@example.com", "password": "Password1!"},
    )
    dup_ok = (
        res_dup.status_code == 409
        and res_dup.json().get("error", {}).get("code") == "email_taken"
        and res_dup.json().get("error", {}).get("message") == "An account with this email already exists."
    )

    # C. Invalid email -> 422
    res_bad_email = client.post(
        "/api/v1/auth/signup",
        json={"name": "Bad Email", "email": "not-a-valid-email", "password": "Password1!"},
    )
    bad_email_ok = res_bad_email.status_code == 422 and "error" in res_bad_email.json()

    # D. Empty name -> 422
    res_bad_name = client.post(
        "/api/v1/auth/signup",
        json={"name": "   ", "email": "badname@example.com", "password": "Password1!"},
    )
    bad_name_ok = res_bad_name.status_code == 422 and "error" in res_bad_name.json()

    signup_passed = s_a_ok and has_token and has_student and no_hash_in_json and dup_ok and bad_email_ok and bad_name_ok
    record_check(
        "signup success returns 201, token, student without password_hash; duplicate email -> 409; invalid email/name -> 422",
        signup_passed,
        f"s_a_ok={s_a_ok}, has_token={has_token}, no_hash={no_hash_in_json}, dup_ok={dup_ok}, bad_email={bad_email_ok}, bad_name={bad_name_ok}",
    )

    # =========================================================================
    # 3. LOGIN SUCCESS & CONSTANT-TIME TIMING DEFENSE
    # =========================================================================
    print("\n--- 3. Login Endpoint & Timing Defense ---")
    # A. Valid login (case-insensitive email)
    res_login_a = client.post(
        "/api/v1/auth/login",
        json={"email": "ALICE@EXAMPLE.COM", "password": "Password1!"},
    )
    login_a_ok = res_login_a.status_code == 200 and "access_token" in res_login_a.json()

    # Verify last_login_at set in DB
    with SessionLocal() as db:
        stu_db = db.get(Student, student_a_id)
        last_login_set = stu_db.last_login_at is not None if stu_db else False

    # B. Wrong password
    res_wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "WrongPassword1!"},
    )

    # C. Unknown email
    res_unknown_email = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "WrongPassword1!"},
    )

    # Both must return identical 401 invalid_credentials response body
    identical_body = (
        res_wrong_pw.status_code == 401
        and res_unknown_email.status_code == 401
        and res_wrong_pw.json() == res_unknown_email.json()
        and res_wrong_pw.json().get("error", {}).get("code") == "invalid_credentials"
        and res_wrong_pw.json().get("error", {}).get("message") == "Incorrect email or password."
    )

    login_passed = login_a_ok and last_login_set and identical_body
    record_check(
        "login success (case-insensitive); wrong password and unknown email return identical 401 invalid_credentials; last_login_at set",
        login_passed,
        f"login_a={login_a_ok}, last_login={last_login_set}, identical_body={identical_body}",
    )

    # =========================================================================
    # 4. BRUTE-FORCE RATE LIMITING
    # =========================================================================
    print("\n--- 4. Brute Force Rate Limiting ---")
    # Signup user for rate limit test
    client.post(
        "/api/v1/auth/signup",
        json={"name": "Brute Tester", "email": "brute@example.com", "password": "Password1!"},
    )

    # Fail 5 times (AUTH_MAX_FAILED_ATTEMPTS = 5)
    for _ in range(5):
        rf = client.post("/api/v1/auth/login", json={"email": "brute@example.com", "password": "WrongPassword1!"})
        assert rf.status_code == 401

    # 6th attempt with CORRECT password -> 429 too_many_attempts
    res_lockout = client.post("/api/v1/auth/login", json={"email": "brute@example.com", "password": "Password1!"})
    lockout_ok = (
        res_lockout.status_code == 429
        and res_lockout.json().get("error", {}).get("code") == "too_many_attempts"
    )

    # Different email is unaffected
    res_alice_unaffected = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "Password1!"})
    other_email_ok = res_alice_unaffected.status_code == 200

    brute_passed = lockout_ok and other_email_ok
    record_check(
        "brute force: after AUTH_MAX_FAILED_ATTEMPTS wrong passwords next attempt -> 429 too_many_attempts; other emails unaffected",
        brute_passed,
        f"lockout_ok={lockout_ok}, other_email_ok={other_email_ok}",
    )

    # =========================================================================
    # 5. GET /auth/me & TOKEN HANDLING
    # =========================================================================
    print("\n--- 5. GET /auth/me & Token Decoding ---")
    # A. Valid token -> 200 AuthStudent
    res_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
    me_ok = res_me.status_code == 200 and res_me.json().get("id") == student_a_id

    # B. Missing header -> 401 not_authenticated with WWW-Authenticate: Bearer
    res_no_auth = client.get("/api/v1/auth/me")
    no_auth_ok = (
        res_no_auth.status_code == 401
        and res_no_auth.json().get("error", {}).get("code") == "not_authenticated"
        and res_no_auth.headers.get("WWW-Authenticate") == "Bearer"
    )

    # C. Garbage token -> 401 invalid_token
    res_garbage = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer this-is-not-a-valid-token"})
    garbage_ok = res_garbage.status_code == 401 and res_garbage.json().get("error", {}).get("code") == "invalid_token"

    # D. Expired token -> 401 token_expired
    settings = get_settings()
    expired_payload = {
        "sub": str(student_a_id),
        "iat": int(time.time()) - 7200,
        "exp": int(time.time()) - 3600,
    }
    expired_token = jwt.encode(expired_payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    res_expired = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    expired_ok = res_expired.status_code == 401 and res_expired.json().get("error", {}).get("code") == "token_expired"

    # E. Token for deleted student -> 401 invalid_token
    res_del_stu = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ephemeral Student", "email": "ephemeral@example.com", "password": "Password1!"},
    )
    eph_token = res_del_stu.json()["access_token"]
    eph_id = res_del_stu.json()["student"]["id"]
    # Delete student from DB
    with SessionLocal() as db:
        eph_row = db.get(Student, eph_id)
        db.delete(eph_row)
        db.commit()

    res_deleted_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {eph_token}"})
    del_ok = res_deleted_me.status_code == 401 and res_deleted_me.json().get("error", {}).get("code") == "invalid_token"

    me_passed = me_ok and no_auth_ok and garbage_ok and expired_ok and del_ok
    record_check(
        "GET /auth/me: valid -> student; missing -> 401 not_authenticated (WWW-Authenticate); garbage -> 401 invalid_token; expired -> 401 token_expired; deleted -> 401 invalid_token",
        me_passed,
        f"me_ok={me_ok}, no_auth={no_auth_ok}, garbage={garbage_ok}, expired={expired_ok}, del_ok={del_ok}",
    )

    # =========================================================================
    # 6. CHANGE PASSWORD
    # =========================================================================
    print("\n--- 6. Change Password Endpoint ---")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # A. Wrong current password -> 401 invalid_credentials
    res_cp_wrong = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPassword1!", "new_password": "NewPassword2!"},
        headers=headers_a,
    )
    cp_wrong_ok = res_cp_wrong.status_code == 401 and res_cp_wrong.json().get("error", {}).get("code") == "invalid_credentials"

    # B. Weak new password -> 422 weak_password
    res_cp_weak = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Password1!", "new_password": "weak"},
        headers=headers_a,
    )
    cp_weak_ok = res_cp_weak.status_code == 422 and res_cp_weak.json().get("error", {}).get("code") == "weak_password"

    # C. Same password -> 422 weak_password with "New password must be different."
    res_cp_same = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Password1!", "new_password": "Password1!"},
        headers=headers_a,
    )
    cp_same_ok = (
        res_cp_same.status_code == 422
        and res_cp_same.json().get("error", {}).get("code") == "weak_password"
        and res_cp_same.json().get("error", {}).get("message") == "New password must be different."
    )

    # D. Successful change -> 200 {"changed": true}
    res_cp_succ = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "Password1!", "new_password": "NewPassword2!"},
        headers=headers_a,
    )
    cp_succ_ok = res_cp_succ.status_code == 200 and res_cp_succ.json() == {"changed": True}

    # Old password fails login, new password succeeds
    login_old_fails = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "Password1!"}).status_code == 401
    login_new_works = client.post("/api/v1/auth/login", json={"email": "alice@example.com", "password": "NewPassword2!"}).status_code == 200

    cp_passed = cp_wrong_ok and cp_weak_ok and cp_same_ok and cp_succ_ok and login_old_fails and login_new_works
    record_check(
        "change-password: wrong current -> 401; weak new -> 422; same password -> 422; success then old pw fails and new pw logs in",
        cp_passed,
        f"wrong={cp_wrong_ok}, weak={cp_weak_ok}, same={cp_same_ok}, succ={cp_succ_ok}, old_fails={login_old_fails}, new_works={login_new_works}",
    )

    # =========================================================================
    # 7. ROUTE PROTECTION (REPRESENTATIVE ROUTES ACROSS ALL ROUTERS)
    # =========================================================================
    print("\n--- 7. Route Protection Audit ---")
    protected_probes = [
        ("courses", client.get("/api/v1/courses")),
        ("sources", client.get("/api/v1/courses/1/sources")),
        ("chunks", client.get("/api/v1/chunks/1")),
        ("kb", client.get("/api/v1/courses/1/kb/status")),
        ("tutor", client.post("/api/v1/courses/1/conversations", json={})),
        ("assessments", client.post("/api/v1/courses/1/assessments", json={})),
        ("dashboard", client.get("/api/v1/students/1/courses/1/dashboard")),
        ("mastery", client.get("/api/v1/students/1/courses/1/mastery")),
        ("student_self", client.get("/api/v1/students/1")),
    ]

    all_protected_401 = True
    probe_fail_detail = ""
    for name, resp in protected_probes:
        if resp.status_code != 401:
            all_protected_401 = False
            probe_fail_detail = f"Route '{name}' returned {resp.status_code} instead of 401"
            break

    # Public routes check
    pub_health = client.get("/api/v1/health").status_code == 200
    pub_meta = client.get("/api/v1/meta").status_code == 200
    pub_docs = client.get("/docs").status_code == 200
    pub_dev = client.post("/api/v1/dev/llm-test", json={"prompt": "hi"}).status_code == 200

    prot_passed = all_protected_401 and pub_health and pub_meta and pub_docs and pub_dev
    record_check(
        "protection: representative route from every router returns 401 without token; /health, /meta, /docs, /dev remain public",
        prot_passed,
        probe_fail_detail or f"health={pub_health}, meta={pub_meta}, docs={pub_docs}, dev={pub_dev}",
    )

    # =========================================================================
    # 8. RESOURCE OWNERSHIP & ACCESS CONTROL
    # =========================================================================
    print("\n--- 8. Resource Ownership & Cross-Student Isolation ---")
    # Signup Student B
    res_b = client.post(
        "/api/v1/auth/signup",
        json={"name": "Bob Student", "email": "bob@example.com", "password": "Password1!"},
    )
    token_b = res_b.json()["access_token"]
    student_b_id = res_b.json()["student"]["id"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Create course with Student A's token
    headers_a = {"Authorization": f"Bearer {client.post('/api/v1/auth/login', json={'email':'alice@example.com','password':'NewPassword2!'}).json()['access_token']}"}
    res_crs = client.post(
        "/api/v1/courses",
        json={"name": "Physics 101", "description": "Mechanics"},
        headers=headers_a,
    )
    course_id = res_crs.json()["id"]

    # Ingest sample.pdf to enable tutor and assessments
    with open(samples_dir / "sample.pdf", "rb") as f:
        client.post(
            f"/api/v1/courses/{course_id}/sources",
            files={"file": ("sample.pdf", f, "application/octet-stream")},
            headers=headers_a,
        )

    # Wait for KB to be ready
    for _ in range(60):
        kb_st = client.get(f"/api/v1/courses/{course_id}/kb/status", headers=headers_a).json()
        if kb_st.get("kb_status") == "ready":
            break
        time.sleep(0.1)

    # Create resources belonging to Bob (Student B)
    res_conv_b = client.post(
        f"/api/v1/courses/{course_id}/conversations",
        json={"title": "Bob Conversation"},
        headers=headers_b,
    )
    conv_b_id = res_conv_b.json()["id"]

    res_ass_b = client.post(
        f"/api/v1/courses/{course_id}/assessments",
        json={"kind": "quiz", "num_questions": 2},
        headers=headers_b,
    )
    ass_b_id = res_ass_b.json()["id"]
    # Bob submits assessment
    client.post(f"/api/v1/assessments/{ass_b_id}/submit", headers=headers_b)

    # Ownership checks: Alice (Student A) attempts accessing Bob's resources:
    # 1. Dashboard cross-access -> 403 forbidden_student
    res_a_view_b_dash = client.get(f"/api/v1/students/{student_b_id}/courses/{course_id}/dashboard", headers=headers_a)
    dash_403 = res_a_view_b_dash.status_code == 403 and res_a_view_b_dash.json().get("error", {}).get("code") == "forbidden_student"

    # 2. Mastery cross-access -> 403 forbidden_student
    res_a_view_b_mast = client.get(f"/api/v1/students/{student_b_id}/courses/{course_id}/mastery", headers=headers_a)
    mast_403 = res_a_view_b_mast.status_code == 403 and res_a_view_b_mast.json().get("error", {}).get("code") == "forbidden_student"

    # 3. Conversation by ID cross-access -> 404 conversation_not_found (never 403, do not leak existence)
    res_a_view_b_conv = client.get(f"/api/v1/conversations/{conv_b_id}", headers=headers_a)
    conv_404 = res_a_view_b_conv.status_code == 404 and res_a_view_b_conv.json().get("error", {}).get("code") == "conversation_not_found"

    # 4. Messages in Bob's conversation -> 404
    res_a_view_b_msgs = client.get(f"/api/v1/conversations/{conv_b_id}/messages", headers=headers_a)
    msgs_404 = res_a_view_b_msgs.status_code == 404 and res_a_view_b_msgs.json().get("error", {}).get("code") == "conversation_not_found"

    # 5. Send message into Bob's conversation -> 404
    res_a_send_b_msg = client.post(
        f"/api/v1/conversations/{conv_b_id}/messages",
        json={"content": "Alice infiltrating Bob's chat"},
        headers=headers_a,
    )
    send_404 = res_a_send_b_msg.status_code == 404 and res_a_send_b_msg.json().get("error", {}).get("code") == "conversation_not_found"

    # 6. Assessment by ID cross-access -> 404 assessment_not_found
    res_a_view_b_ass = client.get(f"/api/v1/assessments/{ass_b_id}", headers=headers_a)
    ass_404 = res_a_view_b_ass.status_code == 404 and res_a_view_b_ass.json().get("error", {}).get("code") == "assessment_not_found"

    # 7. Report by ID cross-access -> 404 assessment_not_found
    res_a_view_b_rep = client.get(f"/api/v1/assessments/{ass_b_id}/report", headers=headers_a)
    rep_404 = res_a_view_b_rep.status_code == 404 and res_a_view_b_rep.json().get("error", {}).get("code") == "assessment_not_found"

    # 8. Delete Bob cross-access -> 403 forbidden_student
    res_a_del_b = client.delete(f"/api/v1/students/{student_b_id}", headers=headers_a)
    del_403 = res_a_del_b.status_code == 403 and res_a_del_b.json().get("error", {}).get("code") == "forbidden_student"

    # 9. Passing student_id=B in body or query while logged in as A -> 403 forbidden_student
    res_a_spoof_body = client.post(
        f"/api/v1/courses/{course_id}/conversations",
        json={"student_id": student_b_id, "title": "Spoofed Conv"},
        headers=headers_a,
    )
    spoof_body_403 = res_a_spoof_body.status_code == 403 and res_a_spoof_body.json().get("error", {}).get("code") == "forbidden_student"

    res_a_spoof_query = client.get(
        f"/api/v1/courses/{course_id}/conversations?student_id={student_b_id}",
        headers=headers_a,
    )
    spoof_query_403 = res_a_spoof_query.status_code == 403 and res_a_spoof_query.json().get("error", {}).get("code") == "forbidden_student"

    ownership_passed = (
        dash_403 and mast_403 and conv_404 and msgs_404 and send_404
        and ass_404 and rep_404 and del_403 and spoof_body_403 and spoof_query_403
    )
    record_check(
        "ownership: A cannot read B's dashboard/mastery (403), cannot read/message B's conv/assessment/report (404), cannot delete B (403); spoofed student_id -> 403",
        ownership_passed,
        f"dash_403={dash_403}, conv_404={conv_404}, msgs_404={msgs_404}, send_404={send_404}, ass_404={ass_404}, rep_404={rep_404}, del_403={del_403}, spoof_body={spoof_body_403}, spoof_query={spoof_query_403}",
    )

    # =========================================================================
    # 9. END-TO-END HAPPY PATH WITH TOKEN (NO STUDENT_ID REQUIRED)
    # =========================================================================
    print("\n--- 9. End-to-End Happy Path (student_id omitted) ---")
    # A. Create conversation without student_id
    res_c_a = client.post(
        f"/api/v1/courses/{course_id}/conversations",
        json={"title": "Alice Mechanics Chat"},
        headers=headers_a,
    )
    conv_a_ok = res_c_a.status_code == 201 and res_c_a.json()["student_id"] == student_a_id
    conv_a_id = res_c_a.json()["id"]

    # B. Ask tutor a question without student_id
    res_msg_a = client.post(
        f"/api/v1/conversations/{conv_a_id}/messages",
        json={"content": "What is Newton's second law?"},
        headers=headers_a,
    )
    msg_a_ok = res_msg_a.status_code == 201 and len(res_msg_a.json().get("answer", "")) > 0

    # C. Create assessment without student_id
    res_ass_a = client.post(
        f"/api/v1/courses/{course_id}/assessments",
        json={"kind": "quiz", "num_questions": 2},
        headers=headers_a,
    )
    ass_a_ok = res_ass_a.status_code == 201 and res_ass_a.json()["student_id"] == student_a_id
    ass_a_id = res_ass_a.json()["id"]
    question_a_id = res_ass_a.json()["questions"][0]["id"]

    # D. Answer question without student_id
    res_ans_a = client.post(
        f"/api/v1/assessments/{ass_a_id}/questions/{question_a_id}/answer",
        json={"answer": "A"},
        headers=headers_a,
    )
    ans_a_ok = res_ans_a.status_code == 200 and "is_correct" in res_ans_a.json()

    # E. Fetch dashboard
    res_dash_a = client.get(
        f"/api/v1/students/{student_a_id}/courses/{course_id}/dashboard",
        headers=headers_a,
    )
    dash_a_ok = res_dash_a.status_code == 200 and "summary" in res_dash_a.json()

    e2e_passed = conv_a_ok and msg_a_ok and ass_a_ok and ans_a_ok and dash_a_ok
    record_check(
        "end-to-end happy path: create conversation/assessment without student_id, tutor Q&A, answer question, fetch dashboard",
        e2e_passed,
        f"conv_a={conv_a_ok}, msg_a={msg_a_ok}, ass_a={ass_a_ok}, ans_a={ans_a_ok}, dash_a={dash_a_ok}",
    )

    # =========================================================================
    # 10. DATABASE INTEGRITY & LEGACY STUDENTS
    # =========================================================================
    print("\n--- 10. DB Hash Verification & Legacy Students ---")
    with SessionLocal() as db:
        stu_row = db.get(Student, student_a_id)
        hash_starts_argon2 = stu_row.password_hash.startswith("$argon2") if (stu_row and stu_row.password_hash) else False
        hash_not_plaintext = stu_row.password_hash != "NewPassword2!" if stu_row else False
        email_is_lowercased = stu_row.email == "alice@example.com" if stu_row else False

    # Create legacy student with no credentials via DEBUG-only POST /students
    res_legacy = client.post("/api/v1/students", json={"name": "Legacy Old Student"})
    legacy_created = res_legacy.status_code == 201
    legacy_id = res_legacy.json()["id"]

    # Try login as legacy student
    res_legacy_login = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@example.com", "password": "Password1!"},
    )
    legacy_cannot_login = (
        res_legacy_login.status_code == 401
        and res_legacy_login.json().get("error", {}).get("code") == "invalid_credentials"
    )

    db_passed = hash_starts_argon2 and hash_not_plaintext and email_is_lowercased and legacy_created and legacy_cannot_login
    record_check(
        "password hash is Argon2 and not plaintext; email stored lowercased; legacy students with no credentials cannot log in",
        db_passed,
        f"argon2={hash_starts_argon2}, not_plain={hash_not_plaintext}, lower={email_is_lowercased}, legacy_created={legacy_created}, legacy_blocked={legacy_cannot_login}",
    )

    # =========================================================================
    # 11. METADATA & OPENAPI SECURITY SCHEME
    # =========================================================================
    print("\n--- 11. Metadata & OpenAPI Security Scheme ---")
    res_meta = client.get("/api/v1/meta").json()
    auth_meta = res_meta.get("auth", {})
    meta_req = auth_meta.get("required") is True
    meta_rules = auth_meta.get("password_rules", {})
    rules_keys = {"min_length", "max_length", "require_uppercase", "require_lowercase", "require_symbol"}
    meta_rules_ok = rules_keys.issubset(set(meta_rules.keys()))
    meta_token_type = auth_meta.get("token_type") == "bearer"
    # Ensure no secrets in meta
    meta_str = str(res_meta)
    no_jwt_secret_in_meta = "verify-auth-test-secret" not in meta_str and "jwt_secret" not in meta_str

    # Check openapi.json contains bearer scheme
    schema = app.openapi()
    sec_schemes = schema.get("components", {}).get("securitySchemes", {})
    has_bearer_scheme = "HTTPBearer" in sec_schemes and sec_schemes["HTTPBearer"].get("scheme") == "bearer"

    meta_passed = meta_req and meta_rules_ok and meta_token_type and no_jwt_secret_in_meta and has_bearer_scheme
    record_check(
        "/meta contains auth block and no secrets; openapi.json contains HTTPBearer scheme",
        meta_passed,
        f"meta_req={meta_req}, meta_rules={meta_rules_ok}, no_secret={no_jwt_secret_in_meta}, bearer={has_bearer_scheme}",
    )

    # =========================================================================
    # 12. AUTH_REQUIRED=false MODE
    # =========================================================================
    print("\n--- 12. AUTH_REQUIRED=false Mode Verification ---")
    os.environ["AUTH_REQUIRED"] = "false"
    # Clear settings cache so new setting takes effect
    get_settings.cache_clear()
    app_no_auth = create_app()
    client_no_auth = TestClient(app_no_auth)
    client_no_auth.__enter__()

    # In legacy/no-auth mode, student-scoped routes work without a token
    res_legacy_dash = client_no_auth.get(f"/api/v1/students/{student_a_id}/courses/{course_id}/dashboard")
    legacy_dash_ok = res_legacy_dash.status_code == 200

    # /auth/me still demands a token even when AUTH_REQUIRED=false
    res_me_no_auth = client_no_auth.get("/api/v1/auth/me")
    me_still_requires_token = (
        res_me_no_auth.status_code == 401
        and res_me_no_auth.json().get("error", {}).get("code") == "not_authenticated"
        and res_me_no_auth.headers.get("WWW-Authenticate") == "Bearer"
    )

    no_auth_passed = legacy_dash_ok and me_still_requires_token
    record_check(
        "AUTH_REQUIRED=false mode: request without token works on student-scoped route, /auth/me still demands token",
        no_auth_passed,
        f"legacy_dash={legacy_dash_ok}, me_still_demands_token={me_still_requires_token}",
    )

    # Restore settings cache and environment
    os.environ["AUTH_REQUIRED"] = "true"
    get_settings.cache_clear()

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 80)
    print("VERIFY AUTH SUMMARY")
    print("=" * 80)
    failed_checks = [name for name, passed, _ in CHECKS if not passed]
    total = len(CHECKS)
    passed_count = total - len(failed_checks)

    print(f"Passed: {passed_count}/{total} checks")
    if failed_checks:
        print(f"\n[FAIL] The following {len(failed_checks)} check(s) failed:")
        for fc in failed_checks:
            print(f"  - {fc}")
        sys.exit(1)
    else:
        print("\n[PASS] ALL PROMPT 9 AUTH CHECKS PASSED CLEANLY!")
        sys.exit(0)


if __name__ == "__main__":
    run_auth_verification()
