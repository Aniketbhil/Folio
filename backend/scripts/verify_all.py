#!/usr/bin/env python3
"""Master verification runner executing all test suites from Prompts 2 through 8."""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent

TEST_SUITES = [
    ("verify_ingestion.py", "Prompt 2: Ingestion & Parsing"),
    ("verify_kb.py", "Prompt 3: Embeddings & Knowledge Base"),
    ("verify_tutor.py", "Prompt 4: Grounded Tutor Chat"),
    ("verify_quiz.py", "Prompt 5: Assessment Generation & Verifier"),
    ("verify_grading.py", "Prompt 6: Grading, Misconceptions & BKT"),
    ("verify_learner.py", "Prompt 7: Personalization, Dashboard & Decay"),
    ("verify_final.py", "Prompt 8: Production Hardening & Evaluation"),
    ("verify_llm_contract.py", "Regression: Live LLM Contract & Signatures"),
]


def run_all_suites() -> None:
    print("=" * 80)
    print("FOLIO BACKEND — RUNNING COMPLETE TEST AND VERIFICATION SUITE")
    print("=" * 80 + "\n")

    results: List[Tuple[str, str, str, float, str]] = []
    overall_start = time.perf_counter()
    has_failure = False

    for script_name, description in TEST_SUITES:
        script_path = SCRIPTS_DIR / script_name
        if not script_path.exists():
            print(f"[MISSING] {script_name} not found!")
            results.append((script_name, description, "MISSING", 0.0, "File not found"))
            has_failure = True
            continue

        print(f"--> Running {script_name} ({description})...")
        t0 = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        elapsed = time.perf_counter() - t0

        if proc.returncode == 0:
            print(f"    PASSED in {elapsed:.2f}s\n")
            results.append((script_name, description, "PASS", elapsed, ""))
        else:
            print(f"    FAILED in {elapsed:.2f}s!\n")
            print("--- Output excerpt ---")
            lines = proc.stdout.strip().split("\n")
            excerpt = "\n".join(lines[-15:])
            print(excerpt)
            print("----------------------\n")
            results.append((script_name, description, "FAIL", elapsed, excerpt))
            has_failure = True

    total_time = time.perf_counter() - overall_start

    # Print Summary Table
    print("\n" + "=" * 80)
    print("FOLIO BACKEND VERIFICATION SUMMARY TABLE")
    print("=" * 80)
    print(f"{'Script':<22} | {'Description':<38} | {'Status':<6} | {'Time':<7}")
    print("-" * 80)
    for name, desc, status, duration, _ in results:
        status_color = "PASS" if status == "PASS" else "FAIL"
        print(f"{name:<22} | {desc:<38} | {status_color:<6} | {duration:>5.2f}s")
    print("=" * 80)
    print(f"Total time elapsed: {total_time:.2f}s")

    if has_failure:
        print("\n[RESULT] One or more verification suites failed.")
        sys.exit(1)
    else:
        print(f"\n[RESULT] ALL {len(TEST_SUITES)} VERIFICATION SUITES PASSED CLEANLY! Folio backend is verified.")
        sys.exit(0)


if __name__ == "__main__":
    run_all_suites()
