import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Set

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure isolated environment before importing application
TEMP_DIR = tempfile.mkdtemp(prefix="folio_tutor_verify_")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DIR}/test.db"
os.environ["CHROMA_DIR"] = f"{TEMP_DIR}/chroma"
os.environ["UPLOAD_DIR"] = f"{TEMP_DIR}/uploads"
os.environ["LLM_MOCK"] = "true"
os.environ["DEBUG"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["AUTH_REQUIRED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.main import create_app
from app.models.conversation import Conversation, Message
from app.models.source import Chunk
from app.models.topic import ChunkTopic
from app.services.tutor.service import expand_topic_ids, get_tutor_service

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


def wait_for_kb_ready(client: TestClient, course_id: int, timeout: float = 15.0) -> Dict[str, Any]:
    """Poll GET /api/v1/courses/{cid}/kb/status until ready or timeout."""
    start = time.time()
    last_status: Dict[str, Any] = {}
    while time.time() - start < timeout:
        res = client.get(f"/api/v1/courses/{course_id}/kb/status")
        if res.status_code == 200:
            last_status = res.json()
            if last_status.get("kb_status") == "ready":
                return last_status
        time.sleep(0.1)
    return last_status


def run_verification() -> int:
    print("=" * 70)
    print(" Folio Prompt 4: AI Tutor & Grounded Conversations Verification")
    print("=" * 70)
    print(f"Isolated test database: {os.environ['DATABASE_URL']}")
    print(f"Isolated Chroma store:  {os.environ['CHROMA_DIR']}")
    print(f"Isolated Upload dir:    {os.environ['UPLOAD_DIR']}")
    print("-" * 70)

    # 1. Ensure sample files exist
    pdf_path = SAMPLES_DIR / "sample.pdf"
    pptx_path = SAMPLES_DIR / "sample.pptx"
    vtt_path = SAMPLES_DIR / "sample.vtt"

    for p in [pdf_path, pptx_path, vtt_path]:
        if not p.is_file():
            print(f"FAIL: Required sample file {p} is missing. Please generate samples.")
            return 1

    app = create_app()
    client = TestClient(app)
    results: Dict[str, bool] = {}

    with client:
        # Setup Students
        stu1_res = client.post("/api/v1/students", json={"name": "Alice TutorTester", "email": "alice@tutor.edu"})
        assert stu1_res.status_code == 201, f"Failed student 1 creation: {stu1_res.text}"
        student_1_id = stu1_res.json()["id"]

        stu2_res = client.post("/api/v1/students", json={"name": "Bob Intruder", "email": "bob@tutor.edu"})
        assert stu2_res.status_code == 201, f"Failed student 2 creation: {stu2_res.text}"
        student_2_id = stu2_res.json()["id"]

        # Setup Course 1
        crs1_res = client.post("/api/v1/courses", json={"name": "Physics & Mechanics 101", "student_id": student_1_id})
        assert crs1_res.status_code == 201, f"Failed course 1 creation: {crs1_res.text}"
        course_1_id = crs1_res.json()["id"]

        # Ingest sample.pdf
        with open(pdf_path, "rb") as f:
            pdf_res = client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"title": "Newtonian Mechanics Syllabus"},
            )
        assert pdf_res.status_code == 201, f"Upload pdf failed: {pdf_res.text}"

        # Ingest sample.pptx
        with open(pptx_path, "rb") as f:
            pptx_res = client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                data={"title": "Lecture 1 Slides"},
            )
        assert pptx_res.status_code == 201, f"Upload pptx failed: {pptx_res.text}"

        # Ingest sample.vtt with media_url
        with open(vtt_path, "rb") as f:
            vtt_res = client.post(
                f"/api/v1/courses/{course_1_id}/sources",
                files={"file": ("sample.vtt", f, "text/vtt")},
                data={
                    "title": "Discussion Video Section",
                    "media_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                },
            )
        assert vtt_res.status_code == 201, f"Upload vtt failed: {vtt_res.text}"

        # Wait for KB build to finish
        kb_stat = wait_for_kb_ready(client, course_1_id, timeout=15.0)
        assert kb_stat.get("kb_status") == "ready", f"KB not ready: {kb_stat}"

        # Create Tutor Conversation for student 1
        conv_res = client.post(
            f"/api/v1/courses/{course_1_id}/conversations",
            json={"student_id": student_1_id, "title": "New Conversation"},
        )
        assert conv_res.status_code == 201, f"Create conversation failed: {conv_res.text}"
        conversation_id = conv_res.json()["id"]

        # -----------------------------------------------------------------
        # CHECK 1: In-material question
        # -----------------------------------------------------------------
        q1_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "What is Newton's second law of motion?"},
        )
        assert q1_res.status_code == 201, f"In-material message failed: {q1_res.text}"
        q1_data = q1_res.json()

        c1_grounding = q1_data["grounding"] in ("grounded", "partial")
        c1_has_citations = len(q1_data["citations"]) >= 1

        with SessionLocal() as db:
            c1_chunks_exist = all(
                db.get(Chunk, c["chunk_id"]) is not None for c in q1_data["citations"]
            )

        # Check inline citation markers [1], [2], ...
        ans_markers = [int(m) for m in re.findall(r"\[(\d+)\]", q1_data["answer"])]
        expected_markers = [c["ref"] for c in q1_data["citations"]]
        c1_markers_match = (ans_markers == expected_markers) and (
            ans_markers == list(range(1, len(q1_data["citations"]) + 1))
        )

        # Check location fields on citations across different formats
        # Check PDF citation
        pdf_cit = next((c for c in q1_data["citations"] if c["source_type"] == "pdf"), None)
        c1_pdf_loc = pdf_cit is not None and "page" in pdf_cit["location"] and pdf_cit["location"]["page"] is not None

        # Check slide citation format with slide-targeting question
        slide_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "Rocket Propulsion exhaust gases thrust"},
        )
        assert slide_res.status_code == 201
        slide_data = slide_res.json()
        slide_cit = next((c for c in slide_data["citations"] if c["source_type"] == "slide"), None)
        c1_slide_loc = slide_cit is not None and "slide" in slide_cit["location"] and slide_cit["location"]["slide"] is not None

        # Ask a video-specific question to verify video citation format
        vid_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "Explain swimmer pushes back against water inertia"},
        )
        assert vid_res.status_code == 201
        vid_data = vid_res.json()
        vid_cit = next((c for c in vid_data["citations"] if c["source_type"] == "video"), None)
        c1_vid_loc = vid_cit is not None and "start_sec" in vid_cit["location"] and vid_cit["location"]["start_sec"] is not None

        c1_ok = (
            c1_grounding
            and c1_has_citations
            and c1_chunks_exist
            and c1_markers_match
            and c1_pdf_loc
            and c1_slide_loc
            and c1_vid_loc
        )
        results["an in-material question -> grounded/partial, citations exist, markers 1..n match citation list, location fields valid"] = c1_ok

        # -----------------------------------------------------------------
        # CHECK 2: Off-material question
        # -----------------------------------------------------------------
        q2_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "How do I bake sourdough bread with yeast?"},
        )
        assert q2_res.status_code == 201
        q2_data = q2_res.json()

        c2_ok = (
            q2_data["grounding"] == "unsupported"
            and len(q2_data["citations"]) == 0
            and q2_data["outside_knowledge_note"] is None
            and "Outside your material:" not in q2_data["answer"]
        )
        results["an off-material question -> unsupported, zero citations, no outside knowledge in answer"] = c2_ok

        # -----------------------------------------------------------------
        # CHECK 3: Mixed question (partial overlap)
        # -----------------------------------------------------------------
        # "Newton second law baking bread ingredients" -> 3 physics terms match out of 6 query terms = 0.50 overlap
        q3_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "Newton second law baking bread ingredients"},
        )
        assert q3_res.status_code == 201
        q3_data = q3_res.json()

        c3_ok = (
            q3_data["grounding"] == "partial"
            and q3_data["outside_knowledge_note"] is not None
            and len(q3_data["citations"]) > 0
            and "Outside your material:" in q3_data["answer"]
        )
        results["a mixed question that only partly overlaps -> partial with a non-null outside_knowledge_note"] = c3_ok

        # -----------------------------------------------------------------
        # CHECK 4: Small talk greeting
        # -----------------------------------------------------------------
        q4_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "hi"},
        )
        assert q4_res.status_code == 201
        q4_data = q4_res.json()

        c4_ok = (
            q4_data["grounding"] is None
            and len(q4_data["citations"]) == 0
            and q4_data["outside_knowledge_note"] is None
            and "Hello" in q4_data["answer"]
        )
        results["greeting ('hi') -> grounding null, no citations, no retrieval"] = c4_ok

        # -----------------------------------------------------------------
        # CHECK 5: Follow-up message triggers rewrite path
        # -----------------------------------------------------------------
        tutor_svc = get_tutor_service()
        before_rewrites = tutor_svc.rewrite_count

        q5_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": "explain that again"},
        )
        assert q5_res.status_code == 201
        after_rewrites = tutor_svc.rewrite_count

        # Also verify via /dev/ask with history
        dev_rewr_res = client.post(
            "/dev/ask",
            json={
                "course_id": course_1_id,
                "question": "explain that again",
                "history": [
                    {"role": "user", "content": "What is Newton's third law of motion?"},
                    {"role": "assistant", "content": "For every action there is an equal and opposite reaction."},
                ],
            },
        )
        assert dev_rewr_res.status_code == 200
        dev_rewr_data = dev_rewr_res.json()

        c5_ok = (after_rewrites > before_rewrites) and (dev_rewr_data["rewritten_query"] is not None)
        results["follow-up message ('explain that again') triggers the rewrite path"] = c5_ok

        # -----------------------------------------------------------------
        # CHECK 6: Conversation title auto-set & Message history
        # -----------------------------------------------------------------
        conv_check = client.get(f"/api/v1/conversations/{conversation_id}").json()
        c6_title_set = (
            conv_check["title"] != "New Conversation"
            and len(conv_check["title"]) <= 60
            and "Newton" in conv_check["title"]
        )

        hist_res = client.get(f"/api/v1/conversations/{conversation_id}/messages?limit=50&offset=0")
        assert hist_res.status_code == 200
        hist_data = hist_res.json()

        c6_hist_ok = (
            len(hist_data) >= 8
            and hist_data[0]["role"] == "user"
            and hist_data[1]["role"] == "assistant"
            and len(hist_data[1]["citations"]) > 0
        )
        results["conversation title auto-set; message history endpoint returns oldest first with stored citations intact"] = (
            c6_title_set and c6_hist_ok
        )

        # -----------------------------------------------------------------
        # CHECK 7: GET /chunks/{citation.chunk_id} click-through path
        # -----------------------------------------------------------------
        target_chunk_id = q1_data["citations"][0]["chunk_id"]
        chunk_viewer_res = client.get(f"/api/v1/chunks/{target_chunk_id}")
        assert chunk_viewer_res.status_code == 200
        c_view_data = chunk_viewer_res.json()

        c7_ok = (
            c_view_data["chunk"]["id"] == target_chunk_id
            and "text" in c_view_data["chunk"]
            and c_view_data["viewer"]["kind"] in ("pdf_page", "slide", "video_time")
        )
        results["GET /chunks/{citation.chunk_id} works for a returned citation (the click-through path)"] = c7_ok

        # -----------------------------------------------------------------
        # CHECK 8: Error handling & edge cases
        # -----------------------------------------------------------------
        # Wrong student_id -> 403
        e1 = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_2_id, "content": "Can I access this chat?"},
        )
        e1_ok = (e1.status_code == 403) and (e1.json()["error"]["code"] == "forbidden_student")

        # Unknown conversation -> 404
        e2 = client.post(
            "/api/v1/conversations/999999/messages",
            json={"student_id": student_1_id, "content": "Hello?"},
        )
        e2_ok = (e2.status_code == 404) and (e2.json()["error"]["code"] == "conversation_not_found")

        # Empty content -> 422
        e3 = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={"student_id": student_1_id, "content": ""},
        )
        e3_ok = (e3.status_code == 422)

        # Course with no embedded chunks -> 409 no_content
        crs_empty = client.post("/api/v1/courses", json={"name": "Empty Course", "student_id": student_1_id})
        crs_empty_id = crs_empty.json()["id"]
        conv_empty = client.post(
            f"/api/v1/courses/{crs_empty_id}/conversations",
            json={"student_id": student_1_id},
        )
        conv_empty_id = conv_empty.json()["id"]

        e4 = client.post(
            f"/api/v1/conversations/{conv_empty_id}/messages",
            json={"student_id": student_1_id, "content": "Any materials here?"},
        )
        e4_ok = (e4.status_code == 409) and (e4.json()["error"]["code"] == "no_content")

        c8_ok = e1_ok and e2_ok and e3_ok and e4_ok
        results["wrong student_id -> 403; unknown conversation -> 404; empty content -> 422; no embedded chunks -> 409 no_content"] = c8_ok

        # -----------------------------------------------------------------
        # CHECK 9: /dev/ask returns data and persists nothing
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            msg_count_before = db.scalar(select(func.count(Message.id))) or 0

        dev_ask_res = client.post(
            "/dev/ask",
            json={"course_id": course_1_id, "question": "What is Newton's third law of motion?"},
        )
        assert dev_ask_res.status_code == 200
        dev_ask_data = dev_ask_res.json()

        with SessionLocal() as db:
            msg_count_after = db.scalar(select(func.count(Message.id))) or 0

        c9_ok = (
            len(dev_ask_data["top_hits"]) > 0
            and dev_ask_data["gate"] in ("passed", "refused_low_score")
            and dev_ask_data["thresholds"]["min"] == 0.50
            and dev_ask_data["thresholds"]["strong"] == 0.65
            and msg_count_before == msg_count_after
        )
        results["/dev/ask returns top_hits, gate decision and thresholds, and persists nothing (message count unchanged)"] = c9_ok

        # -----------------------------------------------------------------
        # CHECK 10: topic_ids scoping
        # -----------------------------------------------------------------
        topics_res = client.get(f"/api/v1/courses/{course_1_id}/topics").json()
        assert len(topics_res) > 0
        target_root_topic = topics_res[0]
        scoped_tids = [target_root_topic["id"]]

        with SessionLocal() as db:
            expanded_leaf_ids = expand_topic_ids(db, course_1_id, scoped_tids)
            allowed_chunks = set(
                db.scalars(
                    select(ChunkTopic.chunk_id).where(ChunkTopic.topic_id.in_(expanded_leaf_ids))
                ).all()
            )

        scoped_ask_res = client.post(
            f"/api/v1/conversations/{conversation_id}/messages",
            json={
                "student_id": student_1_id,
                "content": "Explain the laws of motion",
                "topic_ids": scoped_tids,
            },
        )
        assert scoped_ask_res.status_code == 201
        scoped_data = scoped_ask_res.json()

        c10_ok = len(scoped_data["citations"]) > 0 and all(
            c["chunk_id"] in allowed_chunks for c in scoped_data["citations"]
        )
        results["topic_ids scoping only returns citations whose chunks belong to those topics (or their leaf descendants)"] = c10_ok

        # -----------------------------------------------------------------
        # CHECK 11: Deleting a conversation removes its messages
        # -----------------------------------------------------------------
        with SessionLocal() as db:
            msgs_in_conv_before = db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            ) or 0
        assert msgs_in_conv_before > 0

        del_conv_res = client.delete(f"/api/v1/conversations/{conversation_id}")
        assert del_conv_res.status_code == 200
        assert del_conv_res.json()["deleted"] is True

        with SessionLocal() as db:
            msgs_in_conv_after = db.scalar(
                select(func.count(Message.id)).where(Message.conversation_id == conversation_id)
            ) or 0
            conv_still_exists = db.get(Conversation, conversation_id) is not None

        c11_ok = (msgs_in_conv_after == 0) and (not conv_still_exists)
        results["deleting a conversation removes its messages"] = c11_ok

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
