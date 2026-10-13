"""Plotting functions for personalization simulations."""

from pathlib import Path
from typing import Dict, List
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eval.personalization.simulator import SimulationResult


def plot_personalization_results(
    results: List[SimulationResult],
    out_dir: Path,
) -> Dict[str, str]:
    """Generate trajectory and efficiency plots and save to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)

    by_archetype: Dict[str, Dict[str, SimulationResult]] = {}
    for r in results:
        by_archetype.setdefault(r.archetype_name, {})[r.arm] = r

    # 1. Trajectory plot (2x2 subplots or 4 lines)
    traj_path = out_dir / "personalization_trajectories.png"
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True, sharey=True)
    axes = axes.flatten()

    for idx, (arch_name, arms) in enumerate(by_archetype.items()):
        ax = axes[idx]
        res_a = arms["arm_a"]
        res_b = arms["arm_b"]
        days = list(range(1, len(res_a.daily_avg_effective_mastery) + 1))

        ax.plot(days, res_a.daily_avg_effective_mastery, label="Arm A (Folio Personalized)", color="#1a73e8", linewidth=2)
        ax.plot(days, res_b.daily_avg_effective_mastery, label="Arm B (Control)", color="#ea4335", linestyle="--", linewidth=1.8)
        ax.axhline(0.80, color="#34a853", linestyle=":", alpha=0.7, label="Mastery Target (0.80)")
        ax.set_title(arch_name, fontsize=11, fontweight="bold")
        ax.set_xlabel("Day")
        ax.set_ylabel("Effective Mastery")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(True, alpha=0.3)
        if idx == 0:
            ax.legend(loc="upper left", fontsize=8)

    plt.tight_layout()
    plt.savefig(traj_path, dpi=150)
    plt.close()

    # 2. Efficiency Bar Chart
    eff_path = out_dir / "personalization_efficiency.png"
    plt.figure(figsize=(9, 5))

    archetype_names = list(by_archetype.keys())
    arm_a_jit = []
    arm_b_jit = []

    for name in archetype_names:
        ra = by_archetype[name]["arm_a"].review_counts
        rb = by_archetype[name]["arm_b"].review_counts
        tot_a = ra["just_in_time"] + ra["too_early"] + ra["too_late"]
        tot_b = rb["just_in_time"] + rb["too_early"] + rb["too_late"]
        arm_a_jit.append(ra["just_in_time"] / tot_a * 100.0 if tot_a > 0 else 0.0)
        arm_b_jit.append(rb["just_in_time"] / tot_b * 100.0 if tot_b > 0 else 0.0)

    import numpy as np
    x = np.arange(len(archetype_names))
    width = 0.35

    plt.bar(x - width/2, arm_a_jit, width, label="Arm A (Folio Personalized)", color="#1a73e8")
    plt.bar(x + width/2, arm_b_jit, width, label="Arm B (Control)", color="#ea4335")

    plt.ylabel("Just-in-Time Review Percentage (%)", fontsize=10)
    plt.title("Review Efficiency: Just-In-Time Review Rate by Archetype", fontsize=12)
    plt.xticks(x, archetype_names, fontsize=9)
    plt.ylim(0, 100)
    plt.legend()
    plt.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(eff_path, dpi=150)
    plt.close()

    return {
        "trajectories_png": str(traj_path),
        "efficiency_png": str(eff_path),
    }
