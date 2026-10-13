#!/usr/bin/env python3
"""Evaluation entrypoint running retrieval, generation, quiz, and personalization suites."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.course import Course
from app.models.source import Chunk
from eval.generation import evaluate_generation
from eval.personalization.metrics import compute_personalization_metrics
from eval.personalization.plots import plot_personalization_results
from eval.personalization.simulator import run_all_simulations
from eval.quiz import evaluate_quiz
from eval.retrieval import evaluate_retrieval
from eval.testset import Testset


def run_evaluation(
    suite: str = "all",
    judge_model: str = "gemini-2.5-flash",
    samples: int = 0,
    course_id: int = 0,
    out_dir_path: str = "./eval_results",
) -> Dict[str, Any]:
    settings = get_settings()
    out_dir = Path(out_dir_path)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Resolve Course ID
    if course_id <= 0:
        with SessionLocal() as db:
            c = db.scalar(select(Course).where(Course.name.like("%PHYS101%")))
            if not c:
                c = db.scalar(select(Course).join(Chunk, Chunk.course_id == Course.id))
            if not c:
                c = db.scalar(select(Course))
            if not c:
                raise RuntimeError("No course found in database. Run `python scripts/seed_demo.py` first.")
            course_id = c.id

    print(f"[Eval] Running evaluation against Course ID: {course_id} on suite '{suite}'")

    # 2. Load Testset
    sample_testset_path = Path(__file__).resolve().parent / "testset.sample.json"
    testset = Testset.load_from_file(sample_testset_path)
    if samples > 0:
        testset.items = testset.items[:samples]
    print(f"[Eval] Loaded testset with {len(testset.items)} items.")

    summary: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "course_id": course_id,
        "suite": suite,
        "suites_run": {},
    }

    # 3. Retrieval Suite
    if suite in ("all", "retrieval"):
        print("[Eval] Evaluating Retrieval & Refusal metrics...")
        retrieval_res = evaluate_retrieval(testset, course_id, out_dir)
        summary["suites_run"]["retrieval"] = retrieval_res

    # 4. Generation Suite
    if suite in ("all", "generation"):
        print("[Eval] Evaluating Tutor Generation metrics...")
        gen_res = evaluate_generation(testset, course_id, out_dir, judge_model=judge_model)
        summary["suites_run"]["generation"] = gen_res

    # 5. Quiz Suite
    if suite in ("all", "quiz"):
        print("[Eval] Evaluating Quiz Question Quality...")
        quiz_res = evaluate_quiz(course_id, out_dir, num_questions=samples if samples > 0 else 20)
        summary["suites_run"]["quiz"] = quiz_res

    # 6. Personalization Suite
    if suite in ("all", "personalization"):
        print("[Eval] Running Personalization 30-day simulations...")
        sim_results = run_all_simulations()
        pers_metrics = compute_personalization_metrics(sim_results)
        plot_files = plot_personalization_results(sim_results, out_dir)
        summary["suites_run"]["personalization"] = {
            "metrics": pers_metrics,
            "artifacts": plot_files,
        }

    # 7. Write summary.json
    json_path = out_dir / "summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # 8. Write summary.txt
    txt_path = out_dir / "summary.txt"
    formatted_table = _format_summary_table(summary)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(formatted_table)

    print("\n" + formatted_table)
    print(f"[Eval] Results written to {out_dir}\n")
    return summary


def _format_summary_table(summary: Dict[str, Any]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append(f"FOLIO EVALUATION REPORT — {summary.get('timestamp')}")
    lines.append(f"Course ID: {summary.get('course_id')} | Suite: {summary.get('suite')}")
    lines.append("=" * 80)

    suites = summary.get("suites_run", {})

    # Retrieval
    if "retrieval" in suites:
        ret = suites["retrieval"]
        lines.append(f"\n--- RETRIEVAL & REFUSAL SUITE (N={ret.get('sample_size')}) ---")
        lines.append(f"{'Metric':<25} | {'Mean':<8} | {'95% CI':<18} | {'Samples':<8}")
        lines.append("-" * 65)
        for name, data in ret.get("metrics", {}).items():
            mean_str = f"{data.get('mean', 0.0):.4f}"
            ci = data.get("ci_95", [0.0, 0.0])
            ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]"
            n_val = ret.get("supported_samples") if "refusal" not in name else ret.get("sample_size")
            lines.append(f"{name:<25} | {mean_str:<8} | {ci_str:<18} | {n_val:<8}")

    # Generation
    if "generation" in suites:
        gen = suites["generation"]
        lines.append(f"\n--- TUTOR GENERATION SUITE ({gen.get('evaluator')}, N={gen.get('sample_size')}) ---")
        lines.append(f"{'Metric':<25} | {'Mean':<8} | {'Std':<8} | {'95% CI':<18}")
        lines.append("-" * 65)
        for name, data in gen.get("metrics", {}).items():
            mean_str = f"{data.get('mean', 0.0):.4f}"
            std_str = f"{data.get('std', 0.0):.4f}"
            ci = data.get("ci_95", [0.0, 0.0])
            ci_str = f"[{ci[0]:.4f}, {ci[1]:.4f}]"
            lines.append(f"{name:<25} | {mean_str:<8} | {std_str:<8} | {ci_str:<18}")
        lines.append(f"Flagged for review (score < 0.70): {gen.get('flagged_count')}")

    # Quiz
    if "quiz" in suites:
        quiz = suites["quiz"]
        lines.append(f"\n--- QUIZ GENERATION SUITE (N={quiz.get('sample_size')}) ---")
        for name, val in quiz.get("metrics", {}).items():
            lines.append(f"{name:<35}: {val}")
        lines.append("Difficulty calibration matrix (requested -> judged):")
        matrix = quiz.get("difficulty_confusion_matrix", {})
        for req, row in matrix.items():
            lines.append(f"  {req:<8} -> {row}")

    # Personalization
    if "personalization" in suites:
        pers = suites["personalization"]["metrics"]
        lines.append("\n--- PERSONALIZATION 30-DAY SIMULATION (Arm A: Folio vs Arm B: Control) ---")
        ov = pers.get("overall", {})
        lines.append(f"Overall Just-in-Time Review Rate: Arm A = {ov.get('arm_a_jit_review_rate')*100:.1f}%, Arm B = {ov.get('arm_b_jit_review_rate')*100:.1f}% (Gain: +{ov.get('jit_relative_gain')*100:.1f}%)")
        lines.append(f"{'Archetype':<20} | {'Arm A Day 30 Eff':<18} | {'Arm B Day 30 Eff':<18} | {'Arm A JIT%':<10} | {'Arm B JIT%':<10}")
        lines.append("-" * 85)
        for arch, d in pers.get("by_archetype", {}).items():
            m_a = d["day_30_effective_mastery"]["arm_a_personalized"]
            m_b = d["day_30_effective_mastery"]["arm_b_control"]
            jit_a = d["just_in_time_review_rate"]["arm_a_personalized"] * 100
            jit_b = d["just_in_time_review_rate"]["arm_b_control"] * 100
            lines.append(f"{arch:<20} | {m_a:<18.4f} | {m_b:<18.4f} | {jit_a:<9.1f}% | {jit_b:<9.1f}%")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Folio Evaluation Harness.")
    parser.add_argument(
        "--suite",
        choices=["all", "retrieval", "generation", "quiz", "personalization"],
        default="all",
        help="Evaluation suite to execute",
    )
    parser.add_argument("--model", default="gemini-2.5-flash", help="Judge model")
    parser.add_argument("--samples", type=int, default=0, help="Limit number of test samples")
    parser.add_argument("--course-id", type=int, default=0, help="Course ID to evaluate against")
    parser.add_argument("--out-dir", default="./eval_results", help="Directory for output files")
    args = parser.parse_args()

    run_evaluation(
        suite=args.suite,
        judge_model=args.model,
        samples=args.samples,
        course_id=args.course_id,
        out_dir_path=args.out_dir,
    )
