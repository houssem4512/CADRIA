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

    project = run.project

    # Find the Proposal to work with:
    # 1. If proposal_id is provided → use it
    # 2. Else → find the latest APPROVED proposal for this project
    # 3. Else → find the latest PENDING proposal
    # 4. Else → None (work with project tasks directly)
    proposal = None
    if proposal_id:
        try:
            proposal = Proposal.objects.select_related("project").get(pk=proposal_id)
        except Proposal.DoesNotExist:
            run.status = AgentRun.Status.FAILED
            run.error_message = f"Proposal #{proposal_id} introuvable"
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_message", "finished_at"])
            return {"status": "FAILED", "error": run.error_message}
    else:
        # Auto-find the latest approved proposal
        proposal = (
            Proposal.objects.filter(project=project, status=Proposal.Status.APPROVED)
            .order_by("-validated_at")
            .first()
        )
        if not proposal:
            # Fall back to latest pending proposal
            proposal = (
                Proposal.objects.filter(project=project, status=Proposal.Status.PENDING)
                .order_by("-created_at")
                .first()
            )
        if proposal:
            logger.info("Agent 2 auto-selected Proposal #%s (status=%s)", proposal.id, proposal.status)

    # Build the tasks list — prefer actual DB tasks (post-materialization),
    # fall back to proposal tasks_payload if no DB tasks exist yet
    from projects.models import Task as TaskModel
    db_tasks = list(project.tasks.all().prefetch_related("work_package", "sprint"))
    if db_tasks:
        tasks_payload = []
        for t in db_tasks:
            # Use getattr for ALL optional fields — the Task model may not
            # have skills_needed, reference, task_type, or description fields
            skills_raw = getattr(t, "skills_needed", None)
            skills_needed = []
            if skills_raw:
                try:
                    skills_needed = json.loads(skills_raw) if isinstance(skills_raw, str) else list(skills_raw)
                except (json.JSONDecodeError, TypeError):
                    skills_needed = []
            tasks_payload.append({
                "ref": getattr(t, "reference", "") or f"T-{t.id:03d}",
                "title": t.title,
                "description": getattr(t, "description", "") or "",
                "type": getattr(t, "task_type", "FEATURE") or "FEATURE",
                "priority": t.priority,
                "estimate_hours": float(getattr(t, "estimate_hours", 0) or 0),
                "skills": skills_needed,
                "sprint": t.sprint.name if t.sprint else "",
            })
        logger.info("Agent 2 using %d tasks from DB", len(tasks_payload))
    elif proposal and proposal.tasks_payload:
        # No DB tasks — use the proposal payload (pre-materialization)
        tasks_payload = proposal.tasks_payload
        logger.info("Agent 2 using %d tasks from Proposal #%s payload", len(tasks_payload), proposal.id)
    else:
        run.status = AgentRun.Status.FAILED
        run.error_message = "Aucune tâche trouvée — ni en base ni dans une proposal. Approuvez d'abord un plan Agent 1."
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        return {"status": "FAILED", "error": run.error_message}

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
    if proposal:
        proposal.assignments.all().delete()
        for a in assignments:
            AssignmentSuggestion.objects.create(
                proposal=proposal,
                task_ref=a["task_ref"],
                task_title=a.get("task_title", ""),
                candidate_id=a["user_id"],
                match_score=a["score"],
                rationale=a.get("rationale", ""),
                matched_skills=[],
                workload_before_hours=a.get("workload_before_hours", 0),
                workload_after_hours=a.get("workload_after_hours", 0),
                accepted=None,  # pending PM review
            )

        # CRITICAL: Reset proposal to PENDING so the "Approuver" button
        # appears in the UI. Without this, the proposal stays APPROVED
        # (from Agent 1's validation) and the PM can't validate the
        # new assignments from Agent 2.
        if proposal.status != Proposal.Status.PENDING:
            old_status = proposal.status
            proposal.status = Proposal.Status.PENDING
            proposal.save(update_fields=["status"])
            logger.info("Proposal #%s status reset from %s to PENDING (new assignments from Agent 2)", proposal.id, old_status)

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
    """Push approved tasks to Jira or Trello.
    
    Credentials are read from:
    1. Integration model (if configured in Connecteurs tab)
    2. Environment variables as fallback (TRELLO_API_KEY, TRELLO_API_TOKEN, TRELLO_BOARD_ID)
    """
    import os
    created: list[dict] = []
    errors: list[str] = []
    api_calls = 0

    # Try to find Integration record, fall back to env vars
    integration = None
    try:
        integration = Integration.objects.filter(project=project, provider=provider).first()
    except Exception:
        pass

    if provider == "TRELLO":
        from .trello_client import TrelloClient, TrelloError

        # Get credentials: Integration model first, then env vars
        if integration:
            api_key = getattr(integration, "workspace", "") or os.environ.get("TRELLO_API_KEY", "")
            api_token = getattr(integration, "base_url", "") or os.environ.get("TRELLO_API_TOKEN", "")
            board_id = getattr(integration, "board_key", "") or os.environ.get("TRELLO_BOARD_ID", "")
        else:
            api_key = os.environ.get("TRELLO_API_KEY", "")
            api_token = os.environ.get("TRELLO_API_TOKEN", "")
            board_id = os.environ.get("TRELLO_BOARD_ID", "")

        if not api_key or not api_token or not board_id:
            errors.append(
                f"Trello credentials missing. Set TRELLO_API_KEY, TRELLO_API_TOKEN, "
                f"TRELLO_BOARD_ID in backend/.env OR configure in Connecteurs tab "
                f"(workspace=api_key, base_url=api_token, board_key=board_id)."
            )
            return created, api_calls, errors

        client = TrelloClient(api_key=api_key, api_token=api_token)

        # Load tasks from DB or proposal
        tasks_to_push = []
        db_tasks = list(project.tasks.all())
        if db_tasks:
            for t in db_tasks:
                tasks_to_push.append({
                    "title": t.title,
                    "description": getattr(t, "description", "") or "",
                    "sprint": t.sprint.name if t.sprint else "Sprint",
                })
        else:
            tasks_to_push = proposal.tasks_payload or []

        # Load sprints
        sprints_to_push = proposal.sprints_payload or []
        if not sprints_to_push:
            # Create sprints from DB
            for s in project.sprints.all():
                sprints_to_push.append({"name": s.name})

        # Create a list per sprint
        sprint_lists: dict[str, str] = {}
        for sprint in sprints_to_push:
            sprint_name = sprint.get("name", sprint.get("sprint", "Sprint"))
            try:
                result = client.create_list(board_id, sprint_name)
                sprint_lists[sprint_name] = result["external_id"]
                created.append(result)
            except TrelloError as e:
                errors.append(f"Trello list error: {e}")

        # Create cards per task
        for task in tasks_to_push:
            try:
                sprint_name = task.get("sprint", "")
                list_id = sprint_lists.get(sprint_name, list(sprint_lists.values())[0] if sprint_lists else "")
                if not list_id:
                    errors.append(f"No Trello list for task '{task.get('title', '?')}'")
                    continue
                result = client.create_card(list_id, task.get("title", ""), task.get("description", ""))
                created.append(result)
                api_calls = client.calls_made
            except TrelloError as e:
                errors.append(f"Trello card error: {e}")

    elif provider == "JIRA":
        from .jira_client import JiraClient, JiraError

        if integration:
            base_url = integration.base_url or os.environ.get("JIRA_BASE_URL", "https://api.atlassian.com")
            api_token = os.environ.get("JIRA_API_TOKEN", "")
            api_user = os.environ.get("JIRA_API_USER", "")
            project_key = integration.board_key or os.environ.get("JIRA_PROJECT_KEY", "CAD")
        else:
            base_url = os.environ.get("JIRA_BASE_URL", "https://api.atlassian.com")
            api_token = os.environ.get("JIRA_API_TOKEN", "")
            api_user = os.environ.get("JIRA_API_USER", "")
            project_key = os.environ.get("JIRA_PROJECT_KEY", "CAD")

        if not api_token:
            errors.append("Jira API token missing. Set JIRA_API_TOKEN in .env")
            return created, api_calls, errors

        client = JiraClient(base_url=base_url, api_token=api_token, api_user=api_user)
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