import os
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
TEMP_DIR = tempfile.mkdtemp(prefix="folio_kb_verify_")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DIR}/test.db"
os.environ["CHROMA_DIR"] = f"{TEMP_DIR}/chroma"
os.environ["UPLOAD_DIR"] = f"{TEMP_DIR}/uploads"
os.environ["LLM_MOCK"] = "true"
os.environ["DEBUG"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["AUTH_REQUIRED"] = "false"

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import Base, SessionLocal, engine
from app.main import create_app
from app.models.source import Chunk, Source
from app.services.kb.service import get_kb_service
from app.services.vector_store import get_vector_store

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


def wait_for_kb_building(client: TestClient, course_id: int, timeout: float = 5.0) -> bool:
    """Poll until status is building."""
    start = time.time()
    while time.time() - start < timeout:
        res = client.get(f"/api/v1/courses/{course_id}/kb/status")
        if res.status_code == 200 and res.json().get("kb_status") == "building":
            return True
        time.sleep(0.05)
    return False


def get_all_topic_ids(nodes: List[Dict[str, Any]]) -> Set[int]:
    """Recursively collect topic IDs from topic tree."""
    ids: Set[int] = set()
    for n in nodes:
        ids.add(n["id"])
        if n.get("children"):
            ids.update(get_all_topic_ids(n["children"]))
    return ids


def has_cycle(edges: List[Dict[str, Any]]) -> bool:
    """Check for cycles in directed graph edges."""
    adj: Dict[int, List[int]] = {}
    for e in edges:
        u = e.get("from") or e.get("from_")
        v = e.get("to")
        if u is not None and v is not None:
            adj.setdefault(u, []).append(v)

    visited: Set[int] = set()
    rec_stack: Set[int] = set()

    def dfs(node: int) -> bool:
        visited.add(node)
        rec_stack.add(node)
        for nbr in adj.get(node, []):
            if nbr not in visited:
                if dfs(nbr):
                    return True
            elif nbr in rec_stack:
                return True
        rec_stack.remove(node)
        return False

    for node in list(adj.keys()):
        if node not in visited:
            if dfs(node):
                return True
    return False


def run_verification() -> int:
    print("=" * 65)
    print(" Folio Prompt 3: Knowledge Base & Retrieval Verification")
    print("=" * 65)
    print(f"Isolated test database: {os.environ['DATABASE_URL']}")
    print(f"Isolated Chroma store:  {os.environ['CHROMA_DIR']}")
    print(f"Isolated Upload dir:    {os.environ['UPLOAD_DIR']}")
    print("-" * 65)

    # Ensure samples exist
    pdf_path = SAMPLES_DIR / "sample.pdf"
    pptx_path = SAMPLES_DIR / "sample.pptx"
    vtt_path = SAMPLES_DIR / "sample.vtt"
    yt_json_path = SAMPLES_DIR / "sample_youtube.json"

    for p in [pdf_path, pptx_path, vtt_path, yt_json_path]:
        if not p.is_file():
            print(f"FAIL: Required sample file {p} is missing. Please generate samples.")
            return 1

    app = create_app()
    client = TestClient(app)

    results: Dict[str, bool] = {}

    with client:
        # 1. Setup Student & Course
        stu_res = client.post("/api/v1/students", json={"name": "Alice Tester", "email": "alice@test.edu"})
        assert stu_res.status_code == 201, f"Failed student creation: {stu_res.text}"
        student_id = stu_res.json()["id"]

        crs_res = client.post("/api/v1/courses", json={"name": "Introduction to Folio Systems", "student_id": student_id})
        assert crs_res.status_code == 201, f"Failed course creation: {crs_res.text}"
        course_id = crs_res.json()["id"]

        print(f"Created Course id: {course_id}")

        # 2. Upload sample.pdf
        with open(pdf_path, "rb") as f:
            pdf_res = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"title": "Operating Systems Syllabus"},
            )
        assert pdf_res.status_code == 201, f"Failed uploading pdf: {pdf_res.text}"
        pdf_src_id = pdf_res.json()["id"]

        # 3. Upload sample.pptx
        with open(pptx_path, "rb") as f:
            pptx_res = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                data={"title": "Lecture 1 Slides"},
            )
        assert pptx_res.status_code == 201, f"Failed uploading pptx: {pptx_res.text}"
        pptx_src_id = pptx_res.json()["id"]

        # 4. Upload sample.vtt
        with open(vtt_path, "rb") as f:
            vtt_res = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": ("sample.vtt", f, "text/vtt")},
                data={"title": "Discussion Section VTT"},
            )
        assert vtt_res.status_code == 201, f"Failed uploading vtt: {vtt_res.text}"
        vtt_src_id = vtt_res.json()["id"]

        # 5. Upload sample_youtube.json with media_url
        with open(yt_json_path, "rb") as f:
            yt_res = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": ("sample_youtube.json", f, "application/json")},
                data={
                    "title": "YouTube Video Lecture",
                    "media_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                },
            )
        assert yt_res.status_code == 201, f"Failed uploading youtube json: {yt_res.text}"
        yt_src_id = yt_res.json()["id"]

        # Wait for KB build to finish
        kb_status = wait_for_kb_ready(client, course_id, timeout=15.0)

        # -------------------------------------------------------------
        # CHECK 1: Chunks embedded=True and Chroma vectors exist
        # -------------------------------------------------------------
        with SessionLocal() as db:
            chunks = list(db.scalars(select(Chunk).where(Chunk.course_id == course_id)).all())

        vstore = get_vector_store()
        all_chunk_ids = [str(c.id) for c in chunks]
        chroma_res = vstore.chunks_collection.get(ids=all_chunk_ids)

        c1_embedded = all(c.embedded for c in chunks) and len(chunks) > 0
        c1_vectors = len(chroma_res["ids"]) == len(chunks)
        results["every ready chunk has embedded=true and a vector exists for it"] = c1_embedded and c1_vectors

        # -------------------------------------------------------------
        # CHECK 2: KB status ready and non-zero counts
        # -------------------------------------------------------------
        counts = kb_status.get("counts", {})
        c2_ok = (
            kb_status.get("kb_status") == "ready"
            and counts.get("topics", 0) > 0
            and counts.get("leaf_topics", 0) > 0
            and counts.get("concepts", 0) > 0
            and counts.get("prerequisites", 0) > 0
        )
        results["kb_status is 'ready', topics/leaf topics/concepts/prereq counts are non-zero"] = c2_ok

        # -------------------------------------------------------------
        # CHECK 3: Topic tree and DAG validity (no cycles)
        # -------------------------------------------------------------
        tree_res = client.get(f"/api/v1/courses/{course_id}/topics")
        tree = tree_res.json()
        c3_tree_valid = len(tree) > 0 and all(n.get("parent_id") is None for n in tree)

        # Check leaves and parents
        for root in tree:
            for child in root.get("children", []):
                if child.get("parent_id") != root["id"]:
                    c3_tree_valid = False

        graph_res = client.get(f"/api/v1/courses/{course_id}/graph")
        graph = graph_res.json()
        c3_no_cycle = not has_cycle(graph.get("edges", []))
        results["the topic tree is valid (every leaf has a parent or is itself root, no cycles in prerequisites)"] = (
            c3_tree_valid and c3_no_cycle
        )

        # -------------------------------------------------------------
        # CHECK 4: Tagged vs untagged chunk counts
        # -------------------------------------------------------------
        total_ch = counts.get("total_chunks", 0)
        tagged_ch = counts.get("tagged_chunks", 0)
        untagged_ch = counts.get("untagged_chunks", 0)
        c4_ok = (total_ch > 0) and (tagged_ch > 0) and (tagged_ch + untagged_ch == total_ch)
        results["tagged vs untagged chunk counts"] = c4_ok

        # -------------------------------------------------------------
        # CHECK 5: GET /chunks/{id} viewer fields & seek_url
        # -------------------------------------------------------------
        with SessionLocal() as db:
            pdf_chunk = db.scalar(select(Chunk).where(Chunk.source_id == pdf_src_id))
            slide_chunk = db.scalar(select(Chunk).where(Chunk.source_id == pptx_src_id))
            yt_chunk = db.scalar(select(Chunk).where(Chunk.source_id == yt_src_id, Chunk.start_sec.is_not(None)))

        pdf_view = client.get(f"/api/v1/chunks/{pdf_chunk.id}").json()
        slide_view = client.get(f"/api/v1/chunks/{slide_chunk.id}").json()
        yt_view = client.get(f"/api/v1/chunks/{yt_chunk.id}").json()

        c5_pdf = (pdf_view["viewer"]["kind"] == "pdf_page") and (pdf_view["viewer"]["page"] is not None)
        c5_slide = (slide_view["viewer"]["kind"] == "slide") and (slide_view["viewer"]["slide"] is not None)
        c5_yt = (
            yt_view["viewer"]["kind"] == "video_time"
            and yt_view["viewer"]["has_timestamps"] is True
            and yt_view.get("media_url") == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            and yt_view.get("seek_url") is not None
            and f"&t={int(yt_chunk.start_sec)}s" in yt_view["seek_url"]
        )
        results["GET /chunks/{id} returns correct viewer fields for one pdf, one slide and one video chunk, plus a seek_url containing the start time for the YouTube-style media_url"] = (
            c5_pdf and c5_slide and c5_yt
        )

        # -------------------------------------------------------------
        # CHECK 6: /dev/search returns citations
        # -------------------------------------------------------------
        search_res = client.get(f"/dev/search?course_id={course_id}&q=system&top_k=6")
        citations = search_res.json()
        c6_ok = (
            search_res.status_code == 200
            and isinstance(citations, list)
            and len(citations) > 0
            and "snippet" in citations[0]
            and "source_title" in citations[0]
            and "open_url" in citations[0]
        )
        results["/dev/search returns citations"] = c6_ok

        # -------------------------------------------------------------
        # CHECK 7: Rebuild twice keeps topic IDs stable
        # -------------------------------------------------------------
        orig_topic_ids = get_all_topic_ids(client.get(f"/api/v1/courses/{course_id}/topics").json())

        # First rebuild
        rb1 = client.post(f"/api/v1/courses/{course_id}/kb/rebuild")
        assert rb1.status_code == 202, f"Rebuild 1 failed: {rb1.text}"
        wait_for_kb_ready(client, course_id)
        rb1_ids = get_all_topic_ids(client.get(f"/api/v1/courses/{course_id}/topics").json())

        # Second rebuild
        rb2 = client.post(f"/api/v1/courses/{course_id}/kb/rebuild")
        assert rb2.status_code == 202, f"Rebuild 2 failed: {rb2.text}"
        wait_for_kb_ready(client, course_id)
        rb2_ids = get_all_topic_ids(client.get(f"/api/v1/courses/{course_id}/topics").json())

        c7_ok = (orig_topic_ids == rb1_ids) and (rb1_ids == rb2_ids) and (len(orig_topic_ids) > 0)
        results["rebuild twice keeps topic IDs stable (compare ids before/after)"] = c7_ok

        # -------------------------------------------------------------
        # CHECK 8: Deleting one source triggers KB refresh and course still ready
        # -------------------------------------------------------------
        del_res = client.delete(f"/api/v1/sources/{vtt_src_id}")
        assert del_res.status_code == 200, f"Delete source failed: {del_res.text}"
        time.sleep(0.3)
        post_del_status = wait_for_kb_ready(client, course_id)
        c8_ok = (post_del_status.get("kb_status") == "ready") and (post_del_status.get("counts", {}).get("total_chunks", 0) < total_ch)
        results["deleting one source triggers a KB refresh and the course still ends 'ready'"] = c8_ok

        # -------------------------------------------------------------
        # CHECK 9: Upload second source while first KB build is running (pending flag)
        # -------------------------------------------------------------
        # Create course_2 to cleanly test pending trigger
        crs2_res = client.post("/api/v1/courses", json={"name": "Pending Concurrency Test Course", "student_id": student_id})
        assert crs2_res.status_code == 201, f"Failed course 2 creation: {crs2_res.text}"
        course_2_id = crs2_res.json()["id"]

        kb_svc = get_kb_service()
        # Add a 0.3s delay to ensure build is actively in-flight during second upload
        kb_svc._build_delay = 0.3

        # Start initial build for course 2
        with open(pdf_path, "rb") as f:
            c2_s1 = client.post(
                f"/api/v1/courses/{course_2_id}/sources",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"title": "Course 2 PDF"},
            )
        assert c2_s1.status_code == 201

        # While course 2 build is running, upload pptx
        with open(pptx_path, "rb") as f:
            c2_s2 = client.post(
                f"/api/v1/courses/{course_2_id}/sources",
                files={"file": ("sample.pptx", f, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                data={"title": "Course 2 PPTX"},
            )
        assert c2_s2.status_code == 201

        # Wait until worker has finished all in-flight and pending builds
        start_wait = time.time()
        while time.time() - start_wait < 15.0:
            if not kb_svc.is_building(course_2_id) and kb_svc.build_count.get(course_2_id, 0) >= 2:
                break
            time.sleep(0.05)

        wait_for_kb_ready(client, course_2_id, timeout=5.0)
        kb_svc._build_delay = 0.0

        # Confirm exactly 2 builds ran (initial build + exactly 1 pending rerun)
        build_runs = kb_svc.build_count.get(course_2_id, 0)
        c9_ok = (build_runs == 2)
        results["upload a second source while the first KB build is running and confirm exactly one extra rebuild happens (pending flag)"] = c9_ok

    # -------------------------------------------------------------
    # Print Compact Report
    # -------------------------------------------------------------
    print()
    print("Verification Checklist:")
    all_passed = True
    for desc, passed in results.items():
        status_str = "PASS" if passed else "FAIL"
        if not passed:
            all_passed = False
        print(f"  [{status_str}] {desc}")

    print()
    print("Final Knowledge Base Counts:")
    print(f"  Topics:          {counts.get('topics')}")
    print(f"  Leaf Topics:     {counts.get('leaf_topics')}")
    print(f"  Concepts:        {counts.get('concepts')}")
    print(f"  Prerequisites:   {counts.get('prerequisites')}")
    print(f"  Total Chunks:    {counts.get('total_chunks')}")
    print(f"  Tagged Chunks:   {counts.get('tagged_chunks')}")
    print(f"  Untagged Chunks: {counts.get('untagged_chunks')}")
    print("-" * 65)

    if all_passed:
        print("OVERALL RESULT: ALL CHECKS PASSED")
        return 0
    else:
        print("OVERALL RESULT: SOME CHECKS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(run_verification())
