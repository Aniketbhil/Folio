"""Retrieval evaluation harness with bootstrap confidence intervals and threshold sweep."""

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.course import Course
from app.models.source import Chunk
from app.services.retrieval import retrieve
from eval.testset import Testset, TestsetItem


def bootstrap_ci(
    values: List[float], n_resamples: int = 1000, alpha: float = 0.05
) -> Tuple[float, float, float]:
    """Compute mean and 95% bootstrap confidence interval [ci_lower, ci_upper]."""
    if not values:
        return 0.0, 0.0, 0.0
    arr = np.array(values, dtype=float)
    mean_val = float(np.mean(arr))
    if len(arr) <= 1:
        return mean_val, mean_val, mean_val

    rng = np.random.default_rng(42)
    indices = rng.integers(0, len(arr), size=(n_resamples, len(arr)))
    resampled_means = np.mean(arr[indices], axis=1)
    lower = float(np.percentile(resampled_means, 100.0 * (alpha / 2.0)))
    upper = float(np.percentile(resampled_means, 100.0 * (1.0 - alpha / 2.0)))
    return mean_val, lower, upper


def _is_chunk_relevant(item: TestsetItem, rc: Any) -> bool:
    """Check if retrieved chunk matches expected IDs or key phrases."""
    c_id = rc.chunk.id
    if item.expected_chunk_ids and c_id in item.expected_chunk_ids:
        return True

    text = (rc.chunk.text + " " + (rc.chunk.section_title or "")).lower()
    for phrase in item.expected_key_phrases:
        if phrase.lower() in text:
            return True
    return False


def evaluate_retrieval(
    testset: Testset,
    course_id: int,
    out_dir: Path,
    top_k: int = 5,
) -> Dict[str, Any]:
    """Execute retrieval evaluation on the given testset."""
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()

    hit_1_list: List[float] = []
    hit_3_list: List[float] = []
    hit_5_list: List[float] = []
    mrr_list: List[float] = []
    ctx_precision_list: List[float] = []
    ctx_recall_list: List[float] = []
    citation_accuracy_list: List[float] = []

    # Store query results for threshold sweep & refusal classification
    evaluated_queries: List[Tuple[TestsetItem, float, List[Any]]] = []

    with SessionLocal() as db:
        for item in testset.items:
            retrieved = retrieve(db=db, course_id=course_id, query=item.question, top_k=top_k)
            max_score = max([c.score for c in retrieved], default=0.0)
            evaluated_queries.append((item, max_score, retrieved))

            # Only compute retrieval ranking metrics on non-refusal (supported) questions
            if not item.expected_refusal and item.expected_key_phrases:
                relevant_ranks = []
                for idx, chunk in enumerate(retrieved):
                    if _is_chunk_relevant(item, chunk):
                        relevant_ranks.append(idx + 1)

                h1 = 1.0 if 1 in relevant_ranks else 0.0
                h3 = 1.0 if any(r <= 3 for r in relevant_ranks) else 0.0
                h5 = 1.0 if any(r <= 5 for r in relevant_ranks) else 0.0
                mrr = 1.0 / relevant_ranks[0] if relevant_ranks else 0.0

                hit_1_list.append(h1)
                hit_3_list.append(h3)
                hit_5_list.append(h5)
                mrr_list.append(mrr)

                # Context precision = rel_retrieved / total_retrieved
                prec = len(relevant_ranks) / len(retrieved) if retrieved else 0.0
                ctx_precision_list.append(prec)

                # Context recall = 1.0 if at least 1 relevant retrieved else 0.0 (or fraction)
                rec = 1.0 if relevant_ranks else 0.0
                ctx_recall_list.append(rec)

                # Citation accuracy: does top chunk match key phrases
                cit_acc = 1.0 if (retrieved and _is_chunk_relevant(item, retrieved[0])) else 0.0
                citation_accuracy_list.append(cit_acc)

    # Threshold sweep from 0.30 to 0.80
    thresholds = [round(t, 2) for t in np.arange(0.30, 0.81, 0.05)]
    sweep_rows: List[Dict[str, Any]] = []

    for tau in thresholds:
        tp, fp, fn, tn = 0, 0, 0, 0
        for item, max_score, _ in evaluated_queries:
            predicted_refusal = max_score < tau
            if item.expected_refusal and predicted_refusal:
                tp += 1
            elif not item.expected_refusal and predicted_refusal:
                fp += 1
            elif item.expected_refusal and not predicted_refusal:
                fn += 1
            else:
                tn += 1

        prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        acc = (tp + tn) / len(evaluated_queries) if evaluated_queries else 0.0

        sweep_rows.append({
            "threshold": tau,
            "refusal_precision": round(prec, 4),
            "refusal_recall": round(rec, 4),
            "refusal_f1": round(f1, 4),
            "accuracy": round(acc, 4),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
        })

    # Save threshold sweep CSV
    csv_path = out_dir / "retrieval_threshold_sweep.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(sweep_rows[0].keys()))
        writer.writeheader()
        writer.writerows(sweep_rows)

    # Save threshold sweep plot
    png_path = out_dir / "retrieval_threshold_sweep.png"
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 5))
        plt.plot(
            [r["threshold"] for r in sweep_rows],
            [r["refusal_precision"] for r in sweep_rows],
            marker="o",
            label="Refusal Precision",
        )
        plt.plot(
            [r["threshold"] for r in sweep_rows],
            [r["refusal_recall"] for r in sweep_rows],
            marker="s",
            label="Refusal Recall",
        )
        plt.plot(
            [r["threshold"] for r in sweep_rows],
            [r["refusal_f1"] for r in sweep_rows],
            marker="^",
            label="Refusal F1",
        )
        tutor_thresh = getattr(settings, "tutor_similarity_threshold", settings.tutor_min_score)
        plt.axvline(
            x=tutor_thresh,
            color="red",
            linestyle="--",
            label=f"Selected threshold ({tutor_thresh})",
        )
        plt.title("Retrieval Refusal Classification vs Threshold", fontsize=12)
        plt.xlabel("Similarity Score Threshold", fontsize=10)
        plt.ylabel("Score", fontsize=10)
        plt.ylim(-0.05, 1.05)
        plt.grid(True, alpha=0.3)
        plt.legend(loc="lower left")
        plt.tight_layout()
        plt.savefig(png_path, dpi=150)
        plt.close()
    except Exception as exc:
        print(f"Warning: could not render plot: {exc}")

    # Standard metrics at current settings threshold
    current_thresh = getattr(settings, "tutor_similarity_threshold", settings.tutor_min_score)
    best_row = min(sweep_rows, key=lambda r: abs(r["threshold"] - current_thresh))

    h1_mean, h1_lo, h1_hi = bootstrap_ci(hit_1_list)
    h3_mean, h3_lo, h3_hi = bootstrap_ci(hit_3_list)
    h5_mean, h5_lo, h5_hi = bootstrap_ci(hit_5_list)
    mrr_mean, mrr_lo, mrr_hi = bootstrap_ci(mrr_list)
    cp_mean, cp_lo, cp_hi = bootstrap_ci(ctx_precision_list)
    cr_mean, cr_lo, cr_hi = bootstrap_ci(ctx_recall_list)
    ca_mean, ca_lo, ca_hi = bootstrap_ci(citation_accuracy_list)

    return {
        "sample_size": len(testset.items),
        "supported_samples": len(hit_1_list),
        "refusal_samples": len(testset.items) - len(hit_1_list),
        "metrics": {
            "hit_at_1": {"mean": round(h1_mean, 4), "ci_95": [round(h1_lo, 4), round(h1_hi, 4)]},
            "hit_at_3": {"mean": round(h3_mean, 4), "ci_95": [round(h3_lo, 4), round(h3_hi, 4)]},
            "hit_at_5": {"mean": round(h5_mean, 4), "ci_95": [round(h5_lo, 4), round(h5_hi, 4)]},
            "mrr": {"mean": round(mrr_mean, 4), "ci_95": [round(mrr_lo, 4), round(mrr_hi, 4)]},
            "context_precision": {"mean": round(cp_mean, 4), "ci_95": [round(cp_lo, 4), round(cp_hi, 4)]},
            "context_recall": {"mean": round(cr_mean, 4), "ci_95": [round(cr_lo, 4), round(cr_hi, 4)]},
            "citation_accuracy": {"mean": round(ca_mean, 4), "ci_95": [round(ca_lo, 4), round(ca_hi, 4)]},
            "refusal_precision": {"mean": best_row["refusal_precision"], "ci_95": [best_row["refusal_precision"], best_row["refusal_precision"]]},
            "refusal_recall": {"mean": best_row["refusal_recall"], "ci_95": [best_row["refusal_recall"], best_row["refusal_recall"]]},
            "refusal_f1": {"mean": best_row["refusal_f1"], "ci_95": [best_row["refusal_f1"], best_row["refusal_f1"]]},
        },
        "artifacts": {
            "threshold_sweep_csv": str(csv_path),
            "threshold_sweep_png": str(png_path),
        },
    }
