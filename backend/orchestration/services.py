"""
Contrat d'intégration du runtime multi-agents.

Ce fichier est VOLONTAIREMENT vide d'implémentation : il définit la frontière
entre la plateforme Cadria et le runtime d'agents (LangGraph / CrewAI /
AutoGen) qui sera branché plus tard.

Pour activer les agents :
  1. implémenter `dispatch()` ci-dessous (appel HTTP au runtime, file Celery,
     ou exécution locale du modèle) ;
  2. renseigner `AgentDefinition.runtime_endpoint` pour chaque agent ;
  3. passer la variable d'environnement `AGENT_RUNTIME_ENABLED=True`.

Tant que ce n'est pas fait, `RunAgentView` crée des exécutions au statut
`SKIPPED` : l'emplacement est réservé, l'UI et la traçabilité sont complètes.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class AgentDispatchResult(dict):
    """Résultat normalisé attendu du runtime."""

    # {
    #   "status": "SUCCEEDED" | "FAILED" | "AWAITING_VALIDATION",
    #   "output": {...},          # JSON conforme à output_schema_hint de l'agent
    #   "step": "…",              # dernière étape exécutée
    #   "tokens_in": 0, "tokens_out": 0,
    #   "latency_ms": 0,
    #   "error": None,
    # }


def dispatch(run) -> AgentDispatchResult:
    """
    Envoie une exécution au runtime de l'agent et met à jour `run`.

    Paramètres
    ----------
    run : orchestration.models.AgentRun
        Exécution déjà persistée, avec `input_payload` et `agent`.

    Contrat d'entrée (run.input_payload)
    ------------------------------------
    Agent 1 (SCOPING)  : {"brief": str, "constraints": {...}, "team": [user_id]}
    Agent 2 (OPS)      : {"proposal_id": int, "provider": "JIRA"|"TRELLO", "dry_run": bool}
    Agent 3 (RISK)     : {"window_days": int, "since": ISO date}

    Contrat de sortie (run.output_payload)
    --------------------------------------
    Agent 1 : {"lots": [...], "tasks": [...], "sprints": [...], "risks": [...],
               "total_estimate_hours": float, "confidence": float}
    Agent 2 : {"created": [...], "assignments": [...], "api_calls": n,
               "errors": [...]}
    Agent 3 : {"risk_score": float, "alerts": [...], "factors": [...]}

    Soulève NotImplementedError tant que le runtime n'est pas branché.
    """
    if run.agent.key == "OPS":
        from agents.ops.service import run_ops
        return run_ops(run)

    raise NotImplementedError(
        "Aucun runtime d'agent branché. Implémentez orchestration.services.dispatch() "
        "puis activez AGENT_RUNTIME_ENABLED=True."
    )


# ---------------------------------------------------------------------------
# Helpers prêts à l'emploi pour l'implémentation future
# ---------------------------------------------------------------------------
def build_scoping_payload(project, brief: str, constraints: dict | None = None) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 1 (cadrage & décomposition)."""
    return {
        "brief": brief or project.brief,
        "project_reference": project.reference,
        "methodology": project.methodology,
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
        "provider": project.external_provider or None,
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
