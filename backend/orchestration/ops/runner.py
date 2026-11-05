"""
Agent 2 — Ops runner.

Flow:
  1. Load the Proposal + its tasks + team members
  2. Compute skill match scores (embedder)
  3. Solve the assignment problem (Hungarian via scipy)
  4. Create AssignmentSuggestion records (status: pending PM acceptance)
  5. If dry_run=False AND the proposal is already APPROVED:
     - Push to Jira/Trello via the connector
     - Create real tickets + apply assignments
  6. Write AuditLog + Notification

This agent is INVOKED AFTER a Proposal is approved (or to preview assignments
before approval via dry_run=True).
"""
from __future__ import annotations
import logging
from typing import Any

from django.utils import timezone

from audit.models import AuditLog
from notifications.models import Notification
from orchestration.models import AgentRun, AssignmentSuggestion, Proposal
from projects.models import Integration

from .embedder import score_match
from .assigner import assign_tasks, compute_load_balance

logger = logging.getLogger(__name__)


def run(run: AgentRun) -> dict[str, Any]:
    started = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.step = "Calcul des assignations"
    run.started_at = started
    run.save(update_fields=["status", "step", "started_at"])

    correlation_id = f"ops-{run.id:08x}"
    payload = run.input_payload or {}
    proposal_id = payload.get("proposal_id")
    provider = payload.get("provider", "JIRA")
    dry_run = payload.get("dry_run", True)

    try:
        proposal = Proposal.objects.select_related("project").get(pk=proposal_id)
    except Proposal.DoesNotExist:
        run.status = AgentRun.Status.FAILED
        run.error_message = f"Proposal #{proposal_id} introuvable"
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        return {"status": "FAILED", "error": run.error_message}

    project = proposal.project
    tasks_payload = proposal.tasks_payload or []
    members = list(project.members.all().prefetch_related("skills__skill"))

    # Build member dicts for the embedder
    member_dicts = []
    for m in members:
        member_dicts.append({
            "id": m.id,
            "name": m.full_name,
            "job_title": m.job_title or "",
            "capacity_hours": float(m.weekly_capacity_hours),
            "skills": [{"name": us.skill.name, "level": us.level} for us in m.skills.all()],
        })

    # Compute match scores
    match_scores: dict[tuple[int, int], float] = {}
    for i, task in enumerate(tasks_payload):
        for j, member in enumerate(member_dicts):
            score, matched, rationale = score_match(task, member)
            match_scores[(i, j)] = score

    # Solve assignment
    current_loads = {m["id"]: 0.0 for m in member_dicts}
    assignments = assign_tasks(tasks_payload, member_dicts, match_scores, current_loads)
    balance_index = compute_load_balance(current_loads)

    # Persist AssignmentSuggestion records (clear previous suggestions first)
    proposal.assignments.all().delete()
    for a in assignments:
        AssignmentSuggestion.objects.create(
            proposal=proposal,
            task_ref=a["task_ref"],
            task_title=a["task_title"],
            candidate_id=a["user_id"],
            match_score=a["score"],
            rationale=a["rationale"],
            matched_skills=[],
            workload_before_hours=a["workload_before_hours"],
            workload_after_hours=a["workload_after_hours"],
            accepted=None,  # pending PM review
        )

    # If not dry_run AND proposal is approved → push to Jira/Trello
    created_external: list[dict] = []
    api_calls = 0
    errors: list[str] = []
    if not dry_run and proposal.status == Proposal.Status.APPROVED:
        try:
            created_external, api_calls, errors = _push_to_external(project, proposal, provider)
        except Exception as e:
            logger.exception("External push failed: %s", e)
            errors.append(str(e))

    # Update the run
    finished = timezone.now()
    latency_ms = int((finished - started).total_seconds() * 1000)
    run.status = AgentRun.Status.SUCCEEDED if not errors else AgentRun.Status.FAILED
    run.step = f"{len(assignments)} assignations calculées" + (" + poussées en externe" if not dry_run else "")
    run.output_payload = {
        "assignments": assignments,
        "load_balance_index": balance_index,
        "created_external": created_external,
        "api_calls": api_calls,
        "errors": errors,
        "dry_run": dry_run,
        "provider": provider,
    }
    run.latency_ms = latency_ms
    run.finished_at = finished
    run.save(update_fields=["status", "step", "output_payload", "latency_ms", "finished_at"])

    # Agent observability
    agent = run.agent
    agent.total_runs = (agent.total_runs or 0) + 1
    agent.successful_runs = (agent.successful_runs or 0) + (1 if not errors else 0)
    agent.failed_runs = (agent.failed_runs or 0) + (1 if errors else 0)
    agent.last_run_at = finished
    agent.save(update_fields=["total_runs", "successful_runs", "failed_runs", "last_run_at"])

    _audit(run, correlation_id, proposal, assignments, balance_index, dry_run, errors)
    _notify(run, proposal, assignments, dry_run)

    return {
        "status": "SUCCEEDED" if not errors else "FAILED",
        "output": run.output_payload,
        "latency_ms": latency_ms,
        "engine": "ops-assigner-v1",
    }


def _push_to_external(project, proposal, provider: str) -> tuple[list[dict], int, list[str]]:
    """Push approved tasks to Jira or Trello. Returns (created, api_calls, errors)."""
    created: list[dict] = []
    errors: list[str] = []
    api_calls = 0

    try:
        integration = Integration.objects.get(project=project, provider=provider)
    except Integration.DoesNotExist:
        errors.append(f"Pas d'intégration {provider} configurée pour ce projet")
        return created, api_calls, errors

    if provider == "JIRA":
        from .jira_client import JiraClient, JiraError
        meta = integration.metadata or {}
        client = JiraClient(
            base_url=integration.base_url or "https://api.atlassian.com",
            api_token=integration.api_token,
            api_user=meta.get("api_user", ""),
        )
        project_key = meta.get("project_key", "CAD")
        for task in proposal.tasks_payload or []:
            try:
                result = client.create_issue(
                    project_key=project_key,
                    summary=task.get("title", ""),
                    description=task.get("description", ""),
                    issue_type="Task",
                )
                created.append(result)
                api_calls = client.calls_made
            except JiraError as e:
                errors.append(f"Jira error on {task.get('ref', '?')}: {e}")
    elif provider == "TRELLO":
        from .trello_client import TrelloClient, TrelloError
        meta = integration.metadata or {}
        client = TrelloClient(
            api_key=meta.get("api_key", ""),
            api_token=integration.api_token,
        )
        board_id = meta.get("board_id", "")
        # Create a list per sprint
        sprint_lists: dict[str, str] = {}
        for sprint in proposal.sprints_payload or []:
            try:
                result = client.create_list(board_id, sprint.get("name", "Sprint"))
                sprint_lists[sprint.get("name", "")] = result["external_id"]
                created.append(result)
            except TrelloError as e:
                errors.append(f"Trello list error: {e}")
        for task in proposal.tasks_payload or []:
            try:
                list_id = sprint_lists.get(task.get("sprint", ""), list(sprint_lists.values())[0] if sprint_lists else "")
                result = client.create_card(list_id, task.get("title", ""), task.get("description", ""))
                created.append(result)
                api_calls = client.calls_made
            except TrelloError as e:
                errors.append(f"Trello card error: {e}")
    else:
        errors.append(f"Provider {provider} non supporté")

    return created, api_calls, errors


def _audit(run, correlation_id, proposal, assignments, balance_index, dry_run, errors):
    AuditLog.objects.create(
        actor=run.triggered_by,
        action=AuditLog.Action.AGENT_RUN,
        severity=AuditLog.Severity.NOTICE if not errors else AuditLog.Severity.WARNING,
        entity_type="Project",
        entity_id=str(run.project.pk),
        entity_label=run.project.name,
        description=(
            f"Agent 2 (Ops) — {len(assignments)} assignations calculées"
            f"{' (dry-run)' if dry_run else ' + push externe'}"
            f", indice d'équilibrage {balance_index}"
            f"{f', {len(errors)} erreurs' if errors else ''}"
        ),
        agent_key="OPS",
        run=run,
        correlation_id=correlation_id,
        metadata={
            "proposal_id": proposal.id,
            "assignments_count": len(assignments),
            "load_balance_index": balance_index,
            "dry_run": dry_run,
            "errors": errors[:5],
        },
    )


def _notify(run, proposal, assignments, dry_run):
    Notification.objects.create(
        user=run.triggered_by,
        category=Notification.Category.AGENT,
        level=Notification.Level.AGENT,
        title=f"Assignations prêtes — {run.project.name}",
        message=(
            f"L'Agent 2 a calculé {len(assignments)} assignations "
            f"{'(dry-run, à valider)' if dry_run else '(appliquées)'}. "
            f"Consultez l'onglet Validation du projet."
        ),
        link=f"/app/projects/{run.project.pk}/validation",
        entity_type="Proposal",
        entity_id=proposal.pk,
        metadata={"agent": "OPS", "proposal_id": proposal.id, "dry_run": dry_run},
    )
