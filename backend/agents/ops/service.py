"""Agent 2 (OPS) : envoie un plan validé vers Trello, de façon idempotente et tracée."""
import time
import uuid

import requests
from django.utils import timezone

from audit.models import AuditLog
from orchestration.models import AgentRun, Proposal

from .trello_client import TrelloClient


def _get_client(provider, project, dry_run):
    if provider == "TRELLO":
        return TrelloClient(board_id=project.external_key, dry_run=dry_run)
    raise ValueError(f"Provider non supporté pour l'instant : {provider}")


def _audit(run, corr, entity, label, description, metadata):
    AuditLog.objects.create(
        actor=run.triggered_by,
        action=AuditLog.Action.AGENT_WRITE,
        severity=AuditLog.Severity.INFO,
        entity_type=type(entity).__name__,
        entity_id=str(entity.pk),
        entity_label=label,
        description=description,
        agent_key="OPS",
        run=run,
        correlation_id=corr,
        metadata=metadata,
    )


def _finish(run, started, status, step, output, error=""):
    run.status = status
    run.step = step
    run.progress = 100
    run.output_payload = output
    run.error_message = error
    run.finished_at = timezone.now()
    run.latency_ms = int((time.monotonic() - started) * 1000)
    run.save()

    agent = run.agent
    agent.total_runs += 1
    if status == AgentRun.Status.SUCCEEDED:
        agent.successful_runs += 1
    else:
        agent.failed_runs += 1
    agent.last_run_at = run.finished_at
    agent.save(update_fields=["total_runs", "successful_runs", "failed_runs", "last_run_at"])
    return run


def _fail(run, started, message):
    output = {"created": [], "assignments": [], "api_calls": 0, "errors": [message]}
    return _finish(run, started, AgentRun.Status.FAILED, message, output, message)


def run_ops(run):
    started = time.monotonic()
    run.started_at = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.save(update_fields=["started_at", "status"])

    payload = run.input_payload or {}
    provider = payload.get("provider", "TRELLO")
    dry_run = payload.get("dry_run", True)
    corr = str(uuid.uuid4())[:8]
    project = run.project
    created, errors = [], []

    proposal = Proposal.objects.filter(pk=payload.get("proposal_id"), project=project).first()
    if not proposal:
        return _fail(run, started, "proposal_id invalide ou hors projet.")

    # Validation humaine : aucune écriture réelle sans plan approuvé.
    approved = (Proposal.Status.APPROVED, Proposal.Status.APPLIED)
    if not dry_run and proposal.status not in approved:
        return _fail(run, started, "Validation humaine requise : plan non approuvé.")
    if not dry_run and not project.external_key:
        return _fail(run, started, "project.external_key (id du board) est vide.")

    try:
        client = _get_client(provider, project, dry_run)
    except ValueError as exc:
        return _fail(run, started, str(exc))

    # 1) Sprints -> listes (idempotent via sprint.external_id)
    list_ids = {}
    for sprint in project.sprints.all():
        if sprint.external_id:
            list_ids[sprint.pk] = sprint.external_id
            continue
        try:
            res = client.create_sprint(sprint.name)
        except (RuntimeError, requests.RequestException) as exc:
            errors.append(f"Sprint « {sprint.name} » : {exc}")
            continue
        list_ids[sprint.pk] = res["id"]
        if not dry_run:
            sprint.external_id = res["id"]
            sprint.save(update_fields=["external_id"])
            _audit(run, corr, sprint, sprint.name, f"Liste Trello créée pour {sprint.name}",
                   {"provider": provider, "external_id": res["id"]})

    # 2) Tâches -> cartes (idempotent via task.external_id)
    for task in project.tasks.filter(external_id=""):
        list_id = list_ids.get(task.sprint_id)
        if not list_id:
            errors.append(f"Tâche « {task.title} » : aucun sprint, ignorée.")
            continue
        try:
            res = client.create_task(list_id, {"title": task.title, "description": task.description})
        except (RuntimeError, requests.RequestException) as exc:
            errors.append(f"Tâche « {task.title} » : {exc}")
            continue
        created.append({
            "entity": "issue", "task_id": task.pk,
            "external_id": res["id"], "external_url": res.get("url", ""), "dry_run": dry_run,
        })
        if not dry_run:
            task.external_id = res["id"]
            task.external_url = res.get("url", "")
            task.save(update_fields=["external_id", "external_url"])
            _audit(run, corr, task, task.title, f"Carte Trello créée : {task.title}",
                   {"provider": provider, "external_id": res["id"]})

    if not dry_run and not errors:
        proposal.status = Proposal.Status.APPLIED
        proposal.save(update_fields=["status"])

    output = {
        "created": created,
        "assignments": [],  # à venir : étape matching
        "api_calls": client.api_calls,
        "errors": errors,
        "dry_run": dry_run,
    }
    ok = bool(created) or not errors
    status = AgentRun.Status.SUCCEEDED if ok else AgentRun.Status.FAILED
    step = "Terminé (simulation)" if dry_run else "Terminé"
    return _finish(run, started, status, step, output, "; ".join(errors))