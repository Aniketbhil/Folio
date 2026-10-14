import os
import sys
import tempfile
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Configure isolated environment before importing application
TEMP_DIR = tempfile.mkdtemp(prefix="folio_ingest_verify_")
os.environ["DATABASE_URL"] = f"sqlite:///{TEMP_DIR}/test.db"
os.environ["CHROMA_DIR"] = f"{TEMP_DIR}/chroma"
os.environ["UPLOAD_DIR"] = f"{TEMP_DIR}/uploads"
os.environ["LLM_MOCK"] = "true"
os.environ["DEBUG"] = "true"
os.environ["AUTO_BUILD_KB"] = "true"
os.environ["AUTH_REQUIRED"] = "false"

from fastapi.testclient import TestClient
from app.main import create_app

def run_verification():
    samples_dir = Path(__file__).resolve().parent.parent / "samples"
    app = create_app()
    client = TestClient(app)
    client.__enter__()

    print("=" * 80)
    print("FOLIO BACKEND - PROMPT 2 INGESTION VERIFICATION")
    print("=" * 80)

    # 1. Health check
    res = client.get("/api/v1/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print("[1] Health Check: OK, mode:", res.json()["llm_mode"])

    # 2. Create test course
    course_res = client.post(
        "/api/v1/courses",
        json={"name": "Physics 101: Mechanics", "description": "Newtonian mechanics lecture course"},
    )
    assert course_res.status_code == 201, f"Create course failed: {course_res.text}"
    course_id = course_res.json()["id"]
    print(f"[2] Created Course ID: {course_id} ('Physics 101: Mechanics')")

    # 3. Test unsupported file type (fake.docx -> 415)
    fake_docx_path = samples_dir / "fake.docx"
    with open(fake_docx_path, "rb") as f:
        res_fake = client.post(
            f"/api/v1/courses/{course_id}/sources",
            files={"file": ("fake.docx", f, "application/octet-stream")},
        )
    print(f"[3] Upload fake.docx -> HTTP {res_fake.status_code}: {res_fake.json()}")
    assert res_fake.status_code == 415
    assert res_fake.json()["error"]["code"] == "unsupported_file_type"

    # 4. Upload all other sample files
    sample_files = [
        "sample.pdf",
        "sample.pptx",
        "sample.vtt",
        "sample.srt",
        "sample_youtube.json",
        "sample_plain.txt",
        "sample_timestamped.txt",
        "empty.pdf",
    ]

    source_records = {}
    for filename in sample_files:
        filepath = samples_dir / filename
        with open(filepath, "rb") as f:
            res_up = client.post(
                f"/api/v1/courses/{course_id}/sources",
                files={"file": (filename, f, "application/octet-stream")},
            )
        assert res_up.status_code == 201, f"Failed upload {filename}: {res_up.text}"
        src_data = res_up.json()
        source_records[filename] = src_data["id"]

    # 5. Poll and collect statuses
    results_table = []
    for filename, src_id in source_records.items():
        res_get = client.get(f"/api/v1/sources/{src_id}")
        assert res_get.status_code == 200
        data = res_get.json()
        results_table.append({
            "filename": filename,
            "source_id": src_id,
            "status": data["status"],
            "num_units": data["num_units"],
            "chunk_count": data["chunk_count"],
            "error": data.get("error") or "",
        })

    print("\n" + "=" * 90)
    print(f"{'Filename':<25} {'Status':<10} {'Units':<8} {'Chunks':<8} {'Error':<35}")
    print("-" * 90)
    for r in results_table:
        err_display = (r["error"][:32] + "...") if len(r["error"]) > 35 else r["error"]
        print(f"{r['filename']:<25} {r['status']:<10} {r['num_units']:<8} {r['chunk_count']:<8} {err_display:<35}")
    print("=" * 90 + "\n")

    # 6. Detailed checks
    # 6a. PDF verification
    pdf_id = source_records["sample.pdf"]
    pdf_chunks_res = client.get(f"/api/v1/sources/{pdf_id}/chunks")
    assert pdf_chunks_res.status_code == 200
    pdf_chunks = pdf_chunks_res.json()
    print(f"[6a] PDF Chunks Count: {len(pdf_chunks)}")
    pages_seen = [c["page_number"] for c in pdf_chunks]
    print(f"     Page numbers in chunks: {pages_seen}")
    assert all(p is not None and p >= 1 for p in pages_seen)
    assert 1 in pages_seen and 5 in pages_seen

    # 6b. PPTX verification
    pptx_id = source_records["sample.pptx"]
    pptx_chunks_res = client.get(f"/api/v1/sources/{pptx_id}/chunks")
    assert pptx_chunks_res.status_code == 200
    pptx_chunks = pptx_chunks_res.json()
    pptx_slides = [c["slide_number"] for c in pptx_chunks]
    print(f"[6b] PPTX Chunks Count: {len(pptx_chunks)}")
    print(f"     Slide numbers in chunks (empty slide 6 skipped): {pptx_slides}")
    assert 6 not in pptx_slides
    assert all(s in pptx_slides for s in [1, 2, 3, 4, 5])
    # Check notes on slide 1 or 3
    has_notes = any("Speaker notes:" in c["text"] for c in pptx_chunks)
    print(f"     Speaker notes extracted: {has_notes}")
    assert has_notes

    # 6c. VTT / SRT / JSON verification
    vtt_id = source_records["sample.vtt"]
    vtt_chunks_res = client.get(f"/api/v1/sources/{vtt_id}/chunks")
    assert vtt_chunks_res.status_code == 200
    vtt_chunks = vtt_chunks_res.json()
    print(f"[6c] VTT Chunks Count: {len(vtt_chunks)}")
    for c in vtt_chunks:
        assert c["start_sec"] is not None and c["end_sec"] is not None
        assert c["start_sec"] <= c["end_sec"]
    print(f"     First chunk window: {vtt_chunks[0]['start_sec']}s - {vtt_chunks[0]['end_sec']}s")

    # 6d. Plain text verification
    plain_id = source_records["sample_plain.txt"]
    plain_src = client.get(f"/api/v1/sources/{plain_id}").json()
    plain_chunks = client.get(f"/api/v1/sources/{plain_id}/chunks").json()
    print(f"[6d] Plain Text Warning: {plain_src['meta'].get('warning')}")
    assert plain_src["meta"].get("has_timestamps") is False
    assert "No timestamps found" in plain_src["meta"].get("warning", "")
    assert all(c["start_sec"] is None and c["end_sec"] is None for c in plain_chunks)

    # 6e. Empty PDF scanned error check
    empty_id = source_records["empty.pdf"]
    empty_src = client.get(f"/api/v1/sources/{empty_id}").json()
    print(f"[6e] Empty PDF Status: {empty_src['status']}, Error: {empty_src['error']}")
    assert empty_src["status"] == "failed"
    assert "scanned PDF" in empty_src["error"]

    # 6f. Re-upload same file -> 409 duplicate_source
    with open(samples_dir / "sample.pdf", "rb") as f:
        dup_res = client.post(
            f"/api/v1/courses/{course_id}/sources",
            files={"file": ("sample.pdf", f, "application/octet-stream")},
        )
    print(f"[6f] Duplicate Upload -> HTTP {dup_res.status_code}: {dup_res.json()}")
    assert dup_res.status_code == 409
    assert dup_res.json()["error"]["code"] == "duplicate_source"

    # 6g. Retry on failed source works
    retry_res = client.post(f"/api/v1/sources/{empty_id}/retry")
    print(f"[6g] Retry on empty.pdf -> HTTP {retry_res.status_code}")
    assert retry_res.status_code == 200
    # Check that retry on non-failed source gives 409
    retry_invalid = client.post(f"/api/v1/sources/{pdf_id}/retry")
    print(f"     Retry on ready source -> HTTP {retry_invalid.status_code}: {retry_invalid.json()}")
    assert retry_invalid.status_code == 409
    assert retry_invalid.json()["error"]["code"] == "invalid_state"

    # 6h. File download endpoint
    file_res = client.get(f"/api/v1/sources/{pdf_id}/file")
    print(f"[6h] GET /sources/{pdf_id}/file -> HTTP {file_res.status_code}, type: {file_res.headers.get('content-type')}")
    assert file_res.status_code == 200
    assert file_res.headers.get("content-type") == "application/pdf"
    assert "inline" in file_res.headers.get("content-disposition", "")

    # 6i. Delete source removes file and chunks
    del_res = client.delete(f"/api/v1/sources/{pdf_id}")
    print(f"[6i] DELETE /sources/{pdf_id} -> HTTP {del_res.status_code}: {del_res.json()}")
    assert del_res.status_code == 200
    assert del_res.json() == {"deleted": True}
    del_verify = client.get(f"/api/v1/sources/{pdf_id}")
    assert del_verify.status_code == 404

    # 6j. Course detail counts reflect reality
    course_detail = client.get(f"/api/v1/courses/{course_id}").json()
    print(f"[6j] Course detail counts: {course_detail['counts']}")
    assert course_detail["counts"]["sources"] > 0
    assert course_detail["counts"]["chunks"] > 0

    print("\nALL INGESTION CHECKS PASSED PERFECTLY!\n")

if __name__ == "__main__":
    run_verification()
