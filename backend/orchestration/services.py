"""
Contrat d'intégration du runtime multi-agents.

Cette version IMPLÉMENTE les 3 agents :
  - Agent 1 (SCOPING) : LLM Groq + RAG SQLite + fallback déterministe
  - Agent 2 (OPS)     : skill matching + Hungarian + connecteurs Jira/Trello
  - Agent 3 (RISK)    : XGBoost + NLP signaux faibles + Celery beat

Chaque agent est implémenté dans son sous-package :
  orchestration/scoping/  → Agent 1
  orchestration/ops/      → Agent 2
  orchestration/risk/     → Agent 3

La fonction `dispatch(run)` route vers le bon runner selon `run.agent.key`.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentDispatchResult(dict):
    """Résultat normalisé attendu du runtime."""


def dispatch(run) -> AgentDispatchResult:
    """
    Envoie une exécution au runtime de l'agent et met à jour `run`.

    Route selon `run.agent.key` :
      - "SCOPING" → orchestration.scoping.runner.run()
      - "OPS"     → orchestration.ops.runner.run()
      - "RISK"    → orchestration.risk.runner.run()

    Returns un dict avec status, output, latency, engine.
    """
    agent_key = run.agent.key if run.agent else ""

    if agent_key == "SCOPING":
        from orchestration.scoping.runner import run as scoping_run
        return AgentDispatchResult(scoping_run(run))

    if agent_key == "OPS":
        from orchestration.ops.runner import run as ops_run
        return AgentDispatchResult(ops_run(run))

    if agent_key == "RISK":
        from orchestration.risk.runner import run as risk_run
        return AgentDispatchResult(risk_run(run))

    # Unknown agent
    run.status = run.Status.FAILED
    run.error_message = f"Agent inconnu : {agent_key!r}"
    run.finished_at = timezone_now()
    run.save(update_fields=["status", "error_message", "finished_at"])
    return AgentDispatchResult({"status": "FAILED", "error": run.error_message, "output": {}})


def timezone_now():
    """Lazy import to avoid Django import cycle at module load."""
    from django.utils import timezone
    return timezone.now()


# ---------------------------------------------------------------------------
# Helpers prêts à l'emploi (conservés depuis la version précédente)
# ---------------------------------------------------------------------------
def build_scoping_payload(project, brief: str, constraints: dict | None = None) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 1 (cadrage & décomposition)."""
    return {
        "brief": brief or getattr(project, "brief", ""),
        "project_reference": project.reference,
        "methodology": getattr(project, "methodology", "SCRUM"),
        "constraints": constraints or {},
        "team": [
            {
                "id": m.id,
                "name": m.full_name,
                "role": m.role,
                "capacity_hours": float(m.weekly_capacity_hours),
                "skills": [{"name": us.skill.name, "level": us.level} for us in m.skills.all()],
            }
            for m in project.members.all()
        ],
    }


def build_ops_payload(proposal, provider: str = "JIRA", dry_run: bool = True) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 2 (intégration Jira/Trello)."""
    return {
        "proposal_id": proposal.id,
        "project_reference": proposal.project.reference,
        "provider": provider,
        "dry_run": dry_run,
        "sprints": proposal.sprints_payload,
        "tasks": proposal.tasks_payload,
        "assignments": [
            {"task_ref": a.task_ref, "user_id": a.candidate_id, "score": float(a.match_score)}
            for a in proposal.assignments.filter(accepted=True)
        ],
    }


def build_risk_payload(project, window_days: int = 30) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 3 (analyse & suivi des risques)."""
    return {
        "project_reference": project.reference,
        "window_days": window_days,
        "provider": getattr(project, "external_provider", None),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "estimate_hours": float(t.estimate_hours),
                "spent_hours": float(t.spent_hours),
                "blocked": t.blocked,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
            for t in project.tasks.all()
        ],
        "comments": [
            {"id": c.id, "body": c.body, "created_at": c.created_at.isoformat()}
            for c in project.comments.all()[:200]
        ],
    }
