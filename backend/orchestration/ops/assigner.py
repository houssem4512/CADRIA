"""
Workload-balanced assignment via the Hungarian algorithm.

Given a list of tasks and a list of team members, computes the optimal
1-to-1 assignment that minimizes total cost, where cost combines:
  - skill mismatch (1 - skill_match_score)
  - current workload pressure

Uses scipy.optimize.linear_sum_assignment. If scipy is unavailable,
falls back to a greedy assignment.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from scipy.optimize import linear_sum_assignment
    import numpy as np
    SCIPY_AVAILABLE = True
except ImportError:
    logger.warning("scipy not installed — using greedy assignment")
    SCIPY_AVAILABLE = False


def assign_tasks(
    tasks: list[dict],
    members: list[dict],
    match_scores: dict[tuple[int, int], float],
    current_loads: dict[int, float] | None = None,
    alpha: float = 0.7,  # weight on skill match
    beta: float = 0.3,   # weight on workload
) -> list[dict[str, Any]]:
    """
    Solve the assignment problem.

    Args:
        tasks: list of task dicts (with "ref" and "estimate_hours")
        members: list of member dicts (with "id" and "capacity_hours")
        match_scores: {(task_idx, member_idx): score 0-1}
        current_loads: {member_id: hours_already_assigned}
        alpha, beta: cost weights

    Returns:
        list of {
            "task_ref": str, "user_id": int, "score": float,
            "workload_before": float, "workload_after": float,
            "rationale": str
        }
    """
    if not tasks or not members:
        return []

    current_loads = current_loads or {m["id"]: 0.0 for m in members}
    capacities = {m["id"]: float(m.get("capacity_hours", 35)) for m in members}

    n_tasks = len(tasks)
    n_members = len(members)

    # Build cost matrix (n_tasks × n_members)
    # Lower cost = better match
    if SCIPY_AVAILABLE:
        cost = np.full((n_tasks, n_members), 1.0)
        for i, task in enumerate(tasks):
            for j, member in enumerate(members):
                score = match_scores.get((i, j), 0.0)
                load = current_loads.get(member["id"], 0.0)
                capacity = capacities.get(member["id"], 35.0)
                load_pressure = min(1.0, load / capacity) if capacity > 0 else 1.0
                cost[i, j] = alpha * (1.0 - score) + beta * load_pressure
        # Solve
        row_ind, col_ind = linear_sum_assignment(cost)
        pairs = list(zip(row_ind, col_ind))
    else:
        # Greedy fallback: sort tasks by descending estimate, assign best member each time
        task_order = sorted(range(n_tasks), key=lambda i: -float(tasks[i].get("estimate_hours", 0)))
        member_used = set()
        pairs = []
        for i in task_order:
            best_j = -1
            best_score = -1
            for j, member in enumerate(members):
                if j in member_used:
                    continue
                score = match_scores.get((i, j), 0.0)
                load = current_loads.get(member["id"], 0.0)
                capacity = capacities.get(member["id"], 35.0)
                load_pressure = min(1.0, load / capacity) if capacity > 0 else 1.0
                combined = alpha * score - beta * load_pressure
                if combined > best_score:
                    best_score = combined
                    best_j = j
            if best_j >= 0:
                pairs.append((i, best_j))
                # Allow multiple tasks per member (don't mark as used)

    results = []
    for i, j in pairs:
        task = tasks[i]
        member = members[j]
        score = match_scores.get((i, j), 0.0)
        load_before = current_loads.get(member["id"], 0.0)
        task_hours = float(task.get("estimate_hours", 0))
        load_after = load_before + task_hours
        # Update running load
        current_loads[member["id"]] = load_after
        results.append({
            "task_ref": task.get("ref", f"T-{i+1}"),
            "task_title": task.get("title", ""),
            "user_id": member["id"],
            "user_name": member.get("name", ""),
            "score": round(score, 3),
            "workload_before_hours": round(load_before, 1),
            "workload_after_hours": round(load_after, 1),
            "capacity_hours": capacities.get(member["id"], 35),
            "rationale": f"Match score {score:.2f}, charge après affectation {load_after:.1f}h / {capacities.get(member['id'], 35)}h",
        })
    return results


def compute_load_balance(loads: dict[int, float]) -> float:
    """
    Compute a load balance index (0-1, 1 = perfectly balanced, 0 = one person has everything).

    Uses the inverse of the Gini coefficient.
    """
    if not loads:
        return 1.0
    values = list(loads.values())
    if sum(values) == 0:
        return 1.0
    n = len(values)
    sorted_vals = sorted(values)
    cumulative = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    gini = cumulative / (n * sum(values)) if sum(values) > 0 else 0
    return round(1 - gini, 3)
