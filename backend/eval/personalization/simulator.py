"""30-day student trajectory simulator comparing Folio personalization (Arm A) to Control (Arm B)."""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.services.learner.forgetting import effective_mastery
from app.services.learner.mastery import bkt_update


@dataclass
class Archetype:
    name: str
    active_days: List[int]
    learn_rate: float
    slip: float
    guess: float
    sessions_per_active_day: int = 3


ARCHETYPES = [
    Archetype(
        name="Crammer",
        active_days=[1, 2, 28, 29],
        learn_rate=0.20,
        slip=0.15,
        guess=0.20,
        sessions_per_active_day=8,
    ),
    Archetype(
        name="Steady learner",
        active_days=list(range(1, 31)),
        learn_rate=0.25,
        slip=0.10,
        guess=0.20,
        sessions_per_active_day=3,
    ),
    Archetype(
        name="Struggling learner",
        active_days=[d for d in range(1, 31) if d % 7 in (1, 2, 3, 4, 5)],
        learn_rate=0.12,
        slip=0.25,
        guess=0.15,
        sessions_per_active_day=3,
    ),
    Archetype(
        name="Fast learner",
        active_days=[d for d in range(1, 31) if d % 2 == 1],
        learn_rate=0.40,
        slip=0.05,
        guess=0.25,
        sessions_per_active_day=3,
    ),
]


@dataclass
class TopicState:
    topic_id: int
    p_mastery: float = 0.10
    correct_count: int = 0
    attempts_count: int = 0
    last_practiced_day: Optional[int] = None


@dataclass
class SimulationResult:
    archetype_name: str
    arm: str  # "arm_a" (Folio) | "arm_b" (Control)
    daily_avg_mastery: List[float]
    daily_avg_effective_mastery: List[float]
    final_topic_masteries: Dict[int, float]
    review_counts: Dict[str, int]  # just_in_time, too_early, too_late, new
    sessions_to_reach_80: Optional[int] = None


def simulate_student(
    archetype: Archetype,
    arm: str,
    num_topics: int = 8,
    total_days: int = 30,
) -> SimulationResult:
    """Simulate a student archetype over 30 days under Arm A or Arm B."""
    settings = get_settings()
    rng = random.Random(42 + hash(archetype.name) + (100 if arm == "arm_a" else 200))

    topics = [TopicState(topic_id=i, p_mastery=settings.bkt_p_init) for i in range(num_topics)]
    review_counts = {"just_in_time": 0, "too_early": 0, "too_late": 0, "new": 0}
    daily_avg_mastery: List[float] = []
    daily_avg_eff: List[float] = []
    sessions_conducted = 0
    sessions_to_80: Optional[int] = None

    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)

    for day in range(1, total_days + 1):
        sim_now = base_time + timedelta(days=day)

        # 1. Calculate effective mastery for all topics
        effective_map = {}
        for t in topics:
            if t.last_practiced_day is None:
                effective_map[t.topic_id] = t.p_mastery
            else:
                last_dt = base_time + timedelta(days=t.last_practiced_day)
                effective_map[t.topic_id] = effective_mastery(
                    p_mastery=t.p_mastery,
                    last_practiced_at=last_dt,
                    correct_count=t.correct_count,
                    now=sim_now,
                )

        # 2. If student is active today, conduct study sessions
        if day in archetype.active_days:
            for _ in range(archetype.sessions_per_active_day):
                sessions_conducted += 1

                # Select topic
                chosen_topic: TopicState
                if arm == "arm_a":
                    # Folio Personalization: prioritize topics needing review or low effective mastery
                    # Categorize candidates
                    due_topics = [t for t in topics if t.last_practiced_day is not None and effective_map[t.topic_id] < 0.65]
                    unpracticed = [t for t in topics if t.last_practiced_day is None]
                    if due_topics:
                        chosen_topic = min(due_topics, key=lambda t: effective_map[t.topic_id])
                    elif unpracticed:
                        chosen_topic = unpracticed[0]
                    else:
                        chosen_topic = min(topics, key=lambda t: effective_map[t.topic_id])
                else:
                    # Control (Arm B): naive sequential round-robin or random selection
                    chosen_topic = topics[(sessions_conducted - 1) % len(topics)]

                # Track review timing category before practicing
                eff = effective_map[chosen_topic.topic_id]
                if chosen_topic.last_practiced_day is None:
                    review_counts["new"] += 1
                elif 0.40 <= eff <= 0.65:
                    review_counts["just_in_time"] += 1
                elif eff > 0.75:
                    review_counts["too_early"] += 1
                else:
                    review_counts["too_late"] += 1

                # Simulate question attempt
                # Probability of being correct given student state
                p_known = chosen_topic.p_mastery
                p_correct = p_known * (1.0 - archetype.slip) + (1.0 - p_known) * archetype.guess
                is_correct = rng.random() < p_correct

                # BKT update
                new_p = bkt_update(
                    p_prior=chosen_topic.p_mastery,
                    score=1.0 if is_correct else 0.0,
                    qtype="mcq",
                    difficulty="medium",
                )
                chosen_topic.p_mastery = new_p
                chosen_topic.attempts_count += 1
                if is_correct:
                    chosen_topic.correct_count += 1
                chosen_topic.last_practiced_day = day

                # Update effective map
                effective_map[chosen_topic.topic_id] = new_p

        # End of day stats
        avg_m = sum(t.p_mastery for t in topics) / len(topics)
        avg_eff = sum(effective_map[t.topic_id] for t in topics) / len(topics)
        daily_avg_mastery.append(round(avg_m, 4))
        daily_avg_eff.append(round(avg_eff, 4))

        if avg_eff >= 0.80 and sessions_to_80 is None:
            sessions_to_80 = sessions_conducted

    return SimulationResult(
        archetype_name=archetype.name,
        arm=arm,
        daily_avg_mastery=daily_avg_mastery,
        daily_avg_effective_mastery=daily_avg_eff,
        final_topic_masteries={t.topic_id: round(t.p_mastery, 4) for t in topics},
        review_counts=review_counts,
        sessions_to_reach_80=sessions_to_80,
    )


def run_all_simulations() -> List[SimulationResult]:
    """Execute simulations for all archetypes across both Arm A and Arm B."""
    results = []
    for arch in ARCHETYPES:
        res_a = simulate_student(arch, arm="arm_a")
        res_b = simulate_student(arch, arm="arm_b")
        results.extend([res_a, res_b])
    return results
