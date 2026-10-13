"""Metrics computation for learner personalization simulations."""

from typing import Any, Dict, List
from eval.personalization.simulator import SimulationResult


def compute_personalization_metrics(results: List[SimulationResult]) -> Dict[str, Any]:
    """Aggregate simulation results into comparative metrics between Arm A and Arm B."""
    by_archetype: Dict[str, Dict[str, SimulationResult]] = {}
    for r in results:
        by_archetype.setdefault(r.archetype_name, {})[r.arm] = r

    summary_by_archetype = {}
    total_jit_a = 0
    total_reviews_a = 0
    total_jit_b = 0
    total_reviews_b = 0

    for arch_name, arms in by_archetype.items():
        res_a = arms["arm_a"]
        res_b = arms["arm_b"]

        rev_a = res_a.review_counts
        rev_b = res_b.review_counts

        total_a = rev_a["just_in_time"] + rev_a["too_early"] + rev_a["too_late"]
        total_b = rev_b["just_in_time"] + rev_b["too_early"] + rev_b["too_late"]

        jit_pct_a = (rev_a["just_in_time"] / total_a) if total_a > 0 else 0.0
        jit_pct_b = (rev_b["just_in_time"] / total_b) if total_b > 0 else 0.0

        total_jit_a += rev_a["just_in_time"]
        total_reviews_a += total_a
        total_jit_b += rev_b["just_in_time"]
        total_reviews_b += total_b

        summary_by_archetype[arch_name] = {
            "day_30_effective_mastery": {
                "arm_a_personalized": res_a.daily_avg_effective_mastery[-1],
                "arm_b_control": res_b.daily_avg_effective_mastery[-1],
            },
            "just_in_time_review_rate": {
                "arm_a_personalized": round(jit_pct_a, 4),
                "arm_b_control": round(jit_pct_b, 4),
            },
            "sessions_to_80_percent": {
                "arm_a_personalized": res_a.sessions_to_reach_80,
                "arm_b_control": res_b.sessions_to_reach_80,
            },
            "review_counts": {
                "arm_a": rev_a,
                "arm_b": rev_b,
            },
        }

    overall_jit_a = (total_jit_a / total_reviews_a) if total_reviews_a > 0 else 0.0
    overall_jit_b = (total_jit_b / total_reviews_b) if total_reviews_b > 0 else 0.0

    return {
        "overall": {
            "arm_a_jit_review_rate": round(overall_jit_a, 4),
            "arm_b_jit_review_rate": round(overall_jit_b, 4),
            "jit_relative_gain": round((overall_jit_a - overall_jit_b) / (overall_jit_b or 1.0), 4),
        },
        "by_archetype": summary_by_archetype,
    }
