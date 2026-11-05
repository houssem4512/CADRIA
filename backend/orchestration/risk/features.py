"""
Feature extraction for the Risk Agent.

Extracts per-task + per-project features used by the XGBoost scorer.
All features are numeric (floats) so they can be fed directly to the model.
"""
from __future__ import annotations
import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone

logger = logging.getLogger(__name__)


def extract_task_features(task) -> dict[str, float]:
    """Extract ML features for a single task.

    Args:
        task: projects.Task instance

    Returns dict of numeric features ready for XGBoost.
    """
    now = timezone.now().date()
    est = float(task.estimate_hours or 0)
    spent = float(task.spent_hours or 0)
    remaining = max(0, est - spent)
    progress = (spent / est) if est > 0 else 0

    overdue_days = 0
    if task.due_date and task.due_date < now and task.status != "DONE":
        overdue_days = (now - task.due_date).days

    return {
        "estimate_hours": est,
        "spent_hours": spent,
        "remaining_hours": remaining,
        "progress": round(progress, 3),
        "overdue_days": overdue_days,
        "is_blocked": 1.0 if task.blocked else 0.0,
        "is_overdue": 1.0 if overdue_days > 0 else 0.0,
        "is_in_progress": 1.0 if task.status == "IN_PROGRESS" else 0.0,
        "is_review": 1.0 if task.status == "REVIEW" else 0.0,
        "is_done": 1.0 if task.status == "DONE" else 0.0,
        "priority_high": 1.0 if task.priority in ("HIGH", "HIGHEST") else 0.0,
        "effort_variance": round(abs(est - spent) / max(est, 1), 3),
    }


def extract_project_features(project) -> dict[str, float]:
    """Extract aggregate features at the project level."""
    tasks = list(project.tasks.all())
    if not tasks:
        return {"total_tasks": 0, "avg_progress": 0, "blocked_ratio": 0, "overdue_ratio": 0, "done_ratio": 0}

    n = len(tasks)
    blocked = sum(1 for t in tasks if t.blocked)
    done = sum(1 for t in tasks if t.status == "DONE")
    overdue = sum(1 for t in tasks if t.is_overdue)
    in_progress = sum(1 for t in tasks if t.status == "IN_PROGRESS")
    total_est = sum(float(t.estimate_hours or 0) for t in tasks)
    total_spent = sum(float(t.spent_hours or 0) for t in tasks)

    return {
        "total_tasks": n,
        "blocked_ratio": round(blocked / n, 3),
        "done_ratio": round(done / n, 3),
        "overdue_ratio": round(overdue / n, 3),
        "in_progress_ratio": round(in_progress / n, 3),
        "avg_progress": round(total_spent / max(total_est, 1), 3),
        "total_estimate_hours": total_est,
        "total_spent_hours": total_spent,
    }


def extract_comment_signals(comments_qs) -> dict[str, float]:
    """Detect weak signals in comments — blocked, waiting, regression keywords."""
    keywords = {
        "blocked": ["bloqué", "bloque", "blocked", "blocker", "impossible"],
        "waiting": ["en attente", "waiting", "attendre", "attente de", "pending"],
        "regression": ["régression", "regression", "cassé", "broken", "bug critique"],
        "scope_creep": ["hors périmètre", "scope creep", "nouveau besoin", "additional"],
    }
    counts = {k: 0 for k in keywords}
    total = comments_qs.count()
    if total == 0:
        return {"comment_blocked_count": 0, "comment_waiting_count": 0, "comment_regression_count": 0,
                "comment_scope_creep_count": 0, "total_comments": 0, "weak_signal_ratio": 0}

    for c in comments_qs[:200]:
        body_lower = (c.body or "").lower()
        for signal, kws in keywords.items():
            if any(kw in body_lower for kw in kws):
                counts[signal] += 1

    weak = sum(counts.values())
    return {
        "comment_blocked_count": counts["blocked"],
        "comment_waiting_count": counts["waiting"],
        "comment_regression_count": counts["regression"],
        "comment_scope_creep_count": counts["scope_creep"],
        "total_comments": total,
        "weak_signal_ratio": round(weak / total, 3),
    }


def build_feature_vector(task, project_features: dict, comment_signals: dict) -> list[float]:
    """Build a single flat feature vector for XGBoost input (per-task)."""
    tf = extract_task_features(task)
    vec = [
        tf["estimate_hours"],
        tf["spent_hours"],
        tf["remaining_hours"],
        tf["progress"],
        tf["overdue_days"],
        tf["is_blocked"],
        tf["is_overdue"],
        tf["is_in_progress"],
        tf["is_review"],
        tf["priority_high"],
        tf["effort_variance"],
        project_features["blocked_ratio"],
        project_features["overdue_ratio"],
        project_features["done_ratio"],
        project_features["in_progress_ratio"],
        project_features["avg_progress"],
        comment_signals["comment_blocked_count"],
        comment_signals["comment_waiting_count"],
        comment_signals["comment_regression_count"],
        comment_signals["weak_signal_ratio"],
    ]
    return vec


FEATURE_NAMES = [
    "estimate_hours", "spent_hours", "remaining_hours", "progress", "overdue_days",
    "is_blocked", "is_overdue", "is_in_progress", "is_review", "priority_high",
    "effort_variance",
    "project_blocked_ratio", "project_overdue_ratio", "project_done_ratio",
    "project_in_progress_ratio", "project_avg_progress",
    "comment_blocked_count", "comment_waiting_count", "comment_regression_count",
    "comment_weak_signal_ratio",
]
