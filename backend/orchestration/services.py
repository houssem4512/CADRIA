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

    Soulève NotImplementedError tant que le runtime n'est pas branché
    (la vue convertit alors l'exécution en SKIPPED : emplacement réservé).

    Quand le runtime est branché (AGENT_RUNTIME_ENABLED=True + endpoint
    configuré), appelle le micro-service de l'agent en HTTP, met à jour
    l'exécution, crée la Proposal (Agent 1) et journalise (audit + notif).
    """
    import uuid

    import httpx
    from django.conf import settings as dj_settings
    from django.utils import timezone

    from audit.models import AuditLog
    from notifications.models import Notification

    from .models import AgentDefinition, AgentRun, Proposal

    agent = run.agent
    key = agent.key
    runtime_cfg = dj_settings.AGENT_RUNTIME
    endpoint = (
        agent.runtime_endpoint or runtime_cfg.get(f"{key}_ENDPOINT", "") or ""
    ).rstrip("/")

    if not runtime_cfg.get("ENABLED") or not endpoint:
        # Comportement "emplacement réservé" conservé pour les agents non branchés.
        raise NotImplementedError(
            "Aucun runtime d'agent branché. Renseignez "
            "AgentDefinition.runtime_endpoint puis activez AGENT_RUNTIME_ENABLED=True."
        )

    project = run.project
    user_payload = run.input_payload or {}
    if key == AgentDefinition.Kind.SCOPING:
        payload = build_scoping_payload(
            project,
            brief=user_payload.get("brief", ""),
            constraints=user_payload.get("constraints"),
        )
    else:
        # OPS / RISK : le runtime reçoit le payload fourni au lancement.
        payload = user_payload

    correlation_id = uuid.uuid4().hex[:8]
    started = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.step = "Appel du runtime agent"
    run.started_at = started
    run.save(update_fields=["status", "step", "started_at"])

    def _finalize(success: bool, data: dict, error: str = "") -> AgentDispatchResult:
        latency = int(data.get("latency_ms") or 0) or int(
            (timezone.now() - started).total_seconds() * 1000
        )
        output = data.get("output") or {}
        run.output_payload = output
        run.tokens_in = int(data.get("tokens_in") or 0)
        run.tokens_out = int(data.get("tokens_out") or 0)
        run.latency_ms = latency
        run.finished_at = timezone.now()

        proposal = None
        if success and key == AgentDefinition.Kind.SCOPING and output:
            proposal = Proposal.objects.create(
                run=run,
                project=project,
                title=f"Plan proposé — {project.name}",
                summary=f"Généré par {agent.name} ({data.get('step', '')[:150]})",
                status=Proposal.Status.PENDING,
                lots_payload=output.get("lots", []),
                tasks_payload=output.get("tasks", []),
                sprints_payload=output.get("sprints", []),
                risks_payload=output.get("risks", []),
                assumptions=output.get("assumptions", []),
                total_estimate_hours=output.get("total_estimate_hours") or 0,
                confidence=output.get("confidence") or 0,
            )
            run.status = AgentRun.Status.AWAITING_VALIDATION
            run.step = "En attente de validation humaine"
        elif success:
            run.status = AgentRun.Status.SUCCEEDED
            run.step = (data.get("step") or "Terminé")[:120]
        else:
            run.status = AgentRun.Status.FAILED
            run.step = "Échec du runtime agent"
            run.error_message = error[:2000]
        run.save()

        agent.total_runs = (agent.total_runs or 0) + 1
        if success:
            agent.successful_runs = (agent.successful_runs or 0) + 1
        else:
            agent.failed_runs = (agent.failed_runs or 0) + 1
        prev = max(agent.total_runs - 1, 0)
        agent.avg_latency_ms = int(
            (agent.avg_latency_ms * prev + latency) / agent.total_runs
        )
        agent.last_run_at = timezone.now()
        agent.save(
            update_fields=["total_runs", "successful_runs", "failed_runs",
                           "avg_latency_ms", "last_run_at"]
        )

        AuditLog.objects.create(
            actor=run.triggered_by,
            action=AuditLog.Action.AGENT_RUN,
            severity=(AuditLog.Severity.NOTICE if success
                      else AuditLog.Severity.CRITICAL),
            entity_type="Project", entity_id=str(project.pk),
            entity_label=project.name,
            description=(f"Exécution {run.status} de « {agent.name} » sur "
                         f"« {project.name} »"),
            agent_key=key, run=run, correlation_id=correlation_id,
            metadata={"endpoint": endpoint,
                      "proposal_id": proposal.pk if proposal else None},
        )
        if run.triggered_by_id:
            Notification.objects.create(
                user=run.triggered_by,
                category=Notification.Category.AGENT,
                level=(Notification.Level.SUCCESS if success
                       else Notification.Level.ERROR),
                title=(f"{agent.short_name or agent.name} — "
                       f"{'plan à valider' if proposal else run.status.lower()}"),
                message=(f"L'exécution sur « {project.name} » est "
                         f"{run.status.lower()}."
                         + (" Validez le plan dans l'onglet Validation."
                            if proposal else "")),
                link=(f"/app/projects/{project.pk}/validation" if proposal
                      else f"/app/projects/{project.pk}/agents"),
                entity_type="AgentRun", entity_id=run.pk,
                metadata={"agent": key, "correlation_id": correlation_id,
                          "proposal_id": proposal.pk if proposal else None},
            )
        return AgentDispatchResult(
            {"status": run.status, "output": output,
             "step": run.step, "tokens_in": run.tokens_in,
             "tokens_out": run.tokens_out, "latency_ms": latency,
             "error": error or None}
        )

    try:
        response = httpx.post(
            f"{endpoint}/run",
            json={"payload": payload, "correlation_id": correlation_id},
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # panne réseau / runtime : échec propre, pas de 500
        logger.exception("Échec d'appel au runtime %s", endpoint)
        return _finalize(False, {}, error=f"{type(exc).__name__}: {exc}"[:500])

    if data.get("status") == "SUCCEEDED" and data.get("output"):
        return _finalize(True, data)
    return _finalize(
        False, data, error=(data.get("error") or "Le runtime n'a pas produit de plan."),
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
