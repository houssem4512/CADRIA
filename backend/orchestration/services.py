"""
Contrat et exécution du runtime multi-agents.

Deux modes sont disponibles via `AGENT_RUNTIME["MODE"]` :

- ``LOCAL`` (défaut) : les moteurs de `orchestration.engines` sont exécutés
  dans le processus Django ;
- ``HTTP`` : chaque agent est appelé sur son `runtime_endpoint`
  (service autonome exposé par `orchestration.runtime_server`).

Dans les deux cas, `dispatch()` persiste l'exécution, crée la `Proposal` de
l'Agent 1, synchronise les suggestions d'assignation de l'Agent 2, matérialise
les alertes de l'Agent 3, puis journalise l'action (audit + notification).
Aucune écriture Jira/Trello n'a lieu sans validation humaine.
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

    Contrat d'entrée (run.input_payload)
    ------------------------------------
    Agent 1 (SCOPING)  : {"brief": str, "constraints": {...}, "team": [user_id]}
    Agent 2 (OPS)      : {"proposal_id": int, "provider": "JIRA"|"TRELLO", "dry_run": bool}
    Agent 3 (RISK)     : {"window_days": int, "since": ISO date}

    Contrat de sortie (run.output_payload)
    --------------------------------------
    Agent 1 : {"lots": [...], "tasks": [...], "sprints": [...], "risks": [...],
               "total_estimate_hours": float, "confidence": float}
    Agent 2 : {"created": [...], "assignments": [...], "suggestions": [...],
               "api_calls": n, "errors": [...]}
    Agent 3 : {"risk_score": float, "alerts": [...], "factors": [...]}
    """
    import uuid

    from django.conf import settings as dj_settings
    from django.utils import timezone

    from audit.models import AuditLog
    from notifications.models import Notification

    from .engines import execute
    from .models import AgentDefinition, AgentRun, Proposal

    agent = run.agent
    key = agent.key
    runtime_cfg = dj_settings.AGENT_RUNTIME
    mode = str(runtime_cfg.get("MODE") or "LOCAL").upper()
    endpoint = (
        agent.runtime_endpoint or runtime_cfg.get(f"{key}_ENDPOINT", "") or ""
    ).rstrip("/")

    if not runtime_cfg.get("ENABLED"):
        raise NotImplementedError(
            "Runtime désactivé. Activez AGENT_RUNTIME_ENABLED=True."
        )
    if mode == "HTTP" and not endpoint:
        raise NotImplementedError(
            "Mode HTTP sélectionné mais aucun runtime_endpoint n'est configuré."
        )

    project = run.project
    user_payload = run.input_payload or {}
    proposal = None

    if key == AgentDefinition.Kind.SCOPING:
        payload = build_scoping_payload(
            project,
            brief=user_payload.get("brief", ""),
            constraints=user_payload.get("constraints"),
        )
    elif key == AgentDefinition.Kind.OPS:
        proposal = _resolve_proposal(project, user_payload)
        payload = (
            build_ops_payload(
                proposal,
                provider=user_payload.get("provider") or project.external_provider or "JIRA",
                dry_run=bool(user_payload.get("dry_run", True)),
            )
            if proposal else {}
        )
    elif key == AgentDefinition.Kind.RISK:
        payload = build_risk_payload(
            project, window_days=int(user_payload.get("window_days") or 30)
        )
    else:
        payload = user_payload

    correlation_id = uuid.uuid4().hex[:8]
    started = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.step = "Appel du runtime agent"
    run.started_at = started
    run.save(update_fields=["status", "step", "started_at"])

    def _finalize(success: bool, data: dict, error: str = "") -> AgentDispatchResult:
        nonlocal proposal
        latency = int(data.get("latency_ms") or 0) or int(
            (timezone.now() - started).total_seconds() * 1000
        )
        output = data.get("output") or {}
        run.output_payload = output
        run.tokens_in = int(data.get("tokens_in") or 0)
        run.tokens_out = int(data.get("tokens_out") or 0)
        run.latency_ms = latency
        run.finished_at = timezone.now()
        created_alerts = 0

        if success and key == AgentDefinition.Kind.SCOPING and output:
            proposal = _upsert_proposal(run, project, agent, output, data.get("step", ""))
            run.status = AgentRun.Status.AWAITING_VALIDATION
            run.step = "En attente de validation humaine"
        elif success and key == AgentDefinition.Kind.OPS:
            if proposal:
                _sync_assignment_suggestions(proposal, output)
            run.status = AgentRun.Status.SUCCEEDED
            run.step = (data.get("step") or "Préparation terminée")[:120]
        elif success and key == AgentDefinition.Kind.RISK:
            created_alerts = _apply_risk_output(project, output)
            run.status = AgentRun.Status.SUCCEEDED
            run.step = (data.get("step") or "Analyse terminée")[:120]
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
            metadata={"mode": mode,
                      "endpoint": endpoint or "local",
                      "proposal_id": proposal.pk if proposal else None,
                      "alerts": created_alerts},
        )

        if run.triggered_by_id and key == AgentDefinition.Kind.RISK and created_alerts:
            Notification.objects.create(
                user=run.triggered_by,
                category=Notification.Category.RISK,
                level=(Notification.Level.ERROR
                       if any(a.get("severity") == "CRITICAL" for a in output.get("alerts", []))
                       else Notification.Level.WARNING),
                title=(f"{agent.short_name or agent.name} — "
                       f"{created_alerts} alerte(s) détectée(s)"),
                message=(f"L'analyse de « {project.name} » a produit "
                         f"{created_alerts} alerte(s). Score global : "
                         f"{float(output.get('risk_score') or 0):.0f}/100."),
                link=f"/app/projects/{project.pk}/risks",
                entity_type="AgentRun", entity_id=run.pk,
                metadata={"agent": key, "correlation_id": correlation_id,
                          "alerts": created_alerts},
            )
        elif run.triggered_by_id:
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

    if key == AgentDefinition.Kind.OPS and proposal is None:
        return _finalize(
            False, {},
            error="Aucune proposition à intégrer. Lancez d'abord l'Agent 1 et validez son plan.",
        )

    try:
        if mode == "HTTP":
            import httpx

            response = httpx.post(
                f"{endpoint}/run",
                json={"payload": payload, "correlation_id": correlation_id},
                timeout=runtime_cfg.get("HTTP_TIMEOUT", 300),
            )
            response.raise_for_status()
            data = response.json()
        else:
            data = execute(key, payload)
    except Exception as exc:  # panne réseau / moteur : échec propre, pas de 500
        logger.exception("Échec du runtime %s (%s)", key, mode)
        return _finalize(False, {}, error=f"{type(exc).__name__}: {exc}"[:500])

    if data.get("status") == "SUCCEEDED" and data.get("output"):
        return _finalize(True, data)
    return _finalize(
        False, data, error=(data.get("error") or "Le runtime n'a pas produit de résultat."),
    )


# ---------------------------------------------------------------------------
# Persistance des sorties d'agents
# ---------------------------------------------------------------------------
def _resolve_proposal(project, payload: dict[str, Any]):
    from .models import Proposal

    proposal_id = payload.get("proposal_id")
    if proposal_id:
        return Proposal.objects.filter(pk=proposal_id, project=project).first()
    return (
        project.proposals.filter(status=Proposal.Status.PENDING).order_by("-created_at").first()
        or project.proposals.order_by("-created_at").first()
    )


def _upsert_proposal(run, project, agent, output: dict[str, Any], step: str):
    from .models import Proposal

    latest = project.proposals.order_by("-version").first()
    version = (latest.version + 1) if latest else 1
    defaults = {
        "project": project,
        "title": f"Plan proposé — {project.name}",
        "summary": f"Généré par {agent.name} ({(step or '')[:150]})",
        "status": Proposal.Status.PENDING,
        "version": version,
        "lots_payload": output.get("lots", []),
        "tasks_payload": output.get("tasks", []),
        "sprints_payload": output.get("sprints", []),
        "risks_payload": output.get("risks", []),
        "assumptions": output.get("assumptions", []),
        "total_estimate_hours": output.get("total_estimate_hours") or 0,
        "confidence": output.get("confidence") or 0,
    }
    proposal = Proposal.objects.filter(run=run).first()
    if proposal is None:
        proposal = Proposal.objects.create(run=run, **defaults)
    else:
        for field, value in defaults.items():
            setattr(proposal, field, value)
        proposal.save()
    return proposal


def _sync_assignment_suggestions(proposal, output: dict[str, Any]) -> None:
    from accounts.models import User

    from .models import AssignmentSuggestion

    for item in output.get("suggestions") or []:
        candidate = User.objects.filter(pk=item.get("user_id"), is_active=True).first()
        if candidate is None or not item.get("task_ref"):
            continue
        AssignmentSuggestion.objects.update_or_create(
            proposal=proposal,
            task_ref=item["task_ref"],
            candidate=candidate,
            defaults={
                "task_title": item.get("task_title", ""),
                "match_score": item.get("match_score") or 0,
                "rationale": item.get("rationale", ""),
                "matched_skills": item.get("matched_skills", []),
                "workload_before_hours": item.get("workload_before_hours") or 0,
                "workload_after_hours": item.get("workload_after_hours") or 0,
            },
        )


def _apply_risk_output(project, output: dict[str, Any]) -> int:
    from projects.models import Project, RiskAlert

    created = 0
    for item in output.get("alerts") or []:
        task_id = item.get("task_id")
        task = project.tasks.filter(pk=task_id).first() if task_id else None
        alert, _ = RiskAlert.objects.update_or_create(
            project=project,
            category=item.get("category") or RiskAlert.Category.DELAY,
            title=item.get("title") or "Alerte de risque",
            task=task,
            defaults={
                "severity": item.get("severity") or RiskAlert.Severity.WARNING,
                "score": item.get("score") or 0,
                "message": item.get("message", ""),
                "factors": item.get("factors", []),
                "recommendation": item.get("recommendation", ""),
            },
        )
        created += 1

    score = float(output.get("risk_score") or 0)
    project.risk_score = score
    if score >= 55:
        project.health = Project.Health.RED
    elif score >= 25:
        project.health = Project.Health.AMBER
    else:
        project.health = Project.Health.GREEN
    project.save(update_fields=["risk_score", "health"])
    return created


# ---------------------------------------------------------------------------
# Construction des charges utiles
# ---------------------------------------------------------------------------
def build_scoping_payload(project, brief: str, constraints: dict | None = None) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 1 (cadrage & décomposition)."""
    merged = dict(constraints or {})
    merged.setdefault("budget", float(project.budget) if project.budget else None)
    merged.setdefault("team_size", project.members.count())
    if project.target_end_date:
        merged.setdefault("deadline", project.target_end_date.isoformat())
    merged.setdefault("methodology", project.methodology)
    return {
        "brief": brief or project.brief,
        "project_name": project.name,
        "summary": project.summary,
        "project_reference": project.reference,
        "methodology": project.methodology,
        "constraints": merged,
        "team": [
            {
                "id": m.id,
                "name": m.full_name,
                "role": m.role,
                "capacity_hours": float(m.weekly_capacity_hours),
                "skills": [{"name": us.skill.name, "level": us.level} for us in m.skills.select_related("skill").all()],
            }
            for m in project.members.prefetch_related("skills__skill").all()
        ],
    }


def build_ops_payload(proposal, provider: str = "JIRA", dry_run: bool = True) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 2 (intégration Jira/Trello & assignation)."""
    project = proposal.project
    return {
        "proposal_id": proposal.id,
        "project_reference": project.reference,
        "provider": provider,
        "dry_run": dry_run,
        "sprints": proposal.sprints_payload,
        "tasks": proposal.tasks_payload,
        "assignments": [
            {"task_ref": a.task_ref, "user_id": a.candidate_id, "score": float(a.match_score)}
            for a in proposal.assignments.filter(accepted=True)
        ],
        "team": [
            {
                "id": m.id,
                "name": m.full_name,
                "role": m.role,
                "capacity_hours": float(m.weekly_capacity_hours),
                "current_load_hours": float(
                    sum(t.estimate_hours for t in m.assigned_tasks.exclude(status="DONE"))
                ),
                "skills": [{"name": us.skill.name, "level": us.level} for us in m.skills.all()],
            }
            for m in project.members.prefetch_related("skills__skill").all()
        ],
    }


def build_risk_payload(project, window_days: int = 30) -> dict[str, Any]:
    """Charge utile envoyée à l'Agent 3 (analyse & suivi des risques)."""
    from datetime import timedelta

    from django.utils import timezone

    since = timezone.now() - timedelta(days=window_days)
    return {
        "project_reference": project.reference,
        "window_days": window_days,
        "provider": project.external_provider or None,
        "budget": float(project.budget) if project.budget else None,
        "budget_consumed": float(project.budget_consumed),
        "progress": float(project.progress or 0),
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "estimate_hours": float(t.estimate_hours),
                "spent_hours": float(t.spent_hours),
                "blocked": t.blocked,
                "blocked_reason": t.blocked_reason,
                "risk_score": float(t.risk_score),
                "due_date": t.due_date.isoformat() if t.due_date else None,
                "lot": t.work_package.name if t.work_package_id else None,
            }
            for t in project.tasks.all()
        ],
        "comments": [
            {"id": c.id, "body": c.body, "weak_signal": c.weak_signal,
             "created_at": c.created_at.isoformat()}
            for c in project.comments.filter(created_at__gte=since)[:200]
        ],
        "members": [
            {
                "id": m.id,
                "name": m.full_name,
                "capacity_hours": float(m.weekly_capacity_hours),
                "load_hours": float(
                    sum(t.estimate_hours for t in m.assigned_tasks.exclude(status="DONE"))
                ),
            }
            for m in project.members.all()
        ],
    }
