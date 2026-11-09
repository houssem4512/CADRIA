"""
Vues d'orchestration.

⚠️ Aucun agent n'est exécuté ici. Le runtime (LangGraph / CrewAI / AutoGen et les
trois agents) n'est pas branché : les lancements créent une exécution
`SKIPPED` qui matérialise l'emplacement réservé et journalise l'intention.
Le contrat d'entrée/sortie est déjà figé — brancher un agent revient à
implémenter `services/agent_runtime.py::dispatch`.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.models import User
from audit.models import AuditLog
from notifications.models import Notification
from projects.models import Project, Sprint, Task, WorkPackage


def _can_pilot(user, project):
    """Lancer les agents et valider les propositions : propriétaire (chef de projet) ou admin."""
    return bool(user and user.is_authenticated
                and (user.is_superuser or user.role == User.Role.ADMIN
                     or project.owner_id == user.pk))

from .models import AgentDefinition, AgentRun, AssignmentSuggestion, Proposal
from .serializers import (
    AgentDefinitionSerializer,
    AgentRunSerializer,
    AssignmentSuggestionSerializer,
    ProposalSerializer,
)


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------
class AgentDefinitionViewSet(ModelViewSet):
    queryset = AgentDefinition.objects.all()
    serializer_class = AgentDefinitionSerializer
    search_fields = ["name", "description"]
    ordering_fields = ["order", "name", "total_runs"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class AgentRunViewSet(ModelViewSet):
    serializer_class = AgentRunSerializer
    filterset_backends = []
    ordering_fields = ["created_at", "status", "latency_ms"]

    def get_queryset(self):
        qs = AgentRun.objects.select_related("agent", "project", "triggered_by").all()
        project = self.request.query_params.get("project")
        agent = self.request.query_params.get("agent")
        state = self.request.query_params.get("status")
        if project:
            qs = qs.filter(project_id=project)
        if agent:
            qs = qs.filter(agent__key=agent)
        if state:
            qs = qs.filter(status=state)
        return qs

    def perform_destroy(self, instance):
        if not (self.request.user.is_superuser or self.request.user.role == "ADMIN"):
            raise permissions.PermissionDenied("Seul un administrateur peut supprimer une exécution.")
        instance.delete()


class ProposalViewSet(ModelViewSet):
    serializer_class = ProposalSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = Proposal.objects.select_related("project", "validated_by", "run").prefetch_related(
            "assignments__candidate"
        )
        project = self.request.query_params.get("project")
        status_ = self.request.query_params.get("status")
        if project:
            qs = qs.filter(project_id=project)
        if status_:
            qs = qs.filter(status=status_)
        if self.request.query_params.get("pending") == "true":
            qs = qs.filter(status=Proposal.Status.PENDING)
        return qs


class RunAgentView(views.APIView):
    """
    Point d'entrée unique pour déclencher un agent.

    POST /api/agents/runs/start/
      { "project": 3, "agent": "SCOPING", "input": {"brief": "..."} }

    Si `AGENT_RUNTIME['ENABLED']` est faux (défaut), l'exécution est créée avec
    le statut SKIPPED : l'emplacement est réservé, la traçabilité est complète,
    mais aucune inférence n'a lieu.
    """

    def post(self, request):
        project_id = request.data.get("project")
        agent_key = request.data.get("agent")
        payload = request.data.get("input") or {}
        try:
            project = Project.objects.get(pk=project_id)
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Projet introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_pilot(request.user, project):
            return Response(
                {"detail": "Réservé au chef de projet propriétaire du projet ou à un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            agent = AgentDefinition.objects.get(key=agent_key)
        except AgentDefinition.DoesNotExist:
            return Response({"detail": "Agent inconnu."}, status=status.HTTP_404_NOT_FOUND)

        if not agent.is_available and not settings.AGENT_RUNTIME["ENABLED"]:
            run = _reserve_run(request, project, agent, payload)
            return Response(
                {
                    "detail": (
                        f"« {agent.name} » est un emplacement réservé : le runtime "
                        "n'est pas encore branché. L'exécution a été journalisée."
                    ),
                    "run": AgentRunSerializer(run).data,
                    "reserved": True,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        run = _dispatch(request, project, agent, payload)
        return Response({"run": AgentRunSerializer(run).data, "reserved": False},
                        status=status.HTTP_202_ACCEPTED)


def _reserve_run(request, project, agent, payload):
    run = AgentRun.objects.create(
        project=project,
        agent=agent,
        triggered_by=request.user,
        trigger=request.data.get("trigger", AgentRun.Trigger.MANUAL),
        status=AgentRun.Status.SKIPPED,
        step="En attente du runtime agent",
        progress=0,
        input_payload=payload,
        output_payload={
            "_reserved": True,
            "_message": "Emplacement réservé — aucun agent branché pour le moment.",
            "_contract": agent.output_schema_hint or {},
        },
    )
    AuditLog.objects.create(
        actor=request.user,
        action=AuditLog.Action.AGENT_RUN,
        severity=AuditLog.Severity.NOTICE,
        entity_type="Project", entity_id=str(project.pk), entity_label=project.name,
        description=f"Lancement de « {agent.name} » — runtime non branché (exécution réservée)",
        agent_key=agent.key, run=run, correlation_id=str(uuid.uuid4())[:8],
        ip_address=_client_ip(request),
        metadata={"payload_keys": list(payload.keys())},
    )
    Notification.objects.create(
        user=request.user,
        category=Notification.Category.AGENT,
        level=Notification.Level.AGENT,
        title=f"{agent.short_name or agent.name} — emplacement réservé",
        message=(
            f"Le lancement de « {agent.name} » sur « {project.name} » a été enregistré. "
            "Branchez le runtime (AGENT_RUNTIME_ENABLED=True) pour obtenir une réponse."
        ),
        link=f"/app/projects/{project.pk}/agents",
        entity_type="AgentRun", entity_id=run.pk,
        metadata={"agent": agent.key, "reserved": True},
    )
    agent.total_runs = (agent.total_runs or 0) + 1
    agent.last_run_at = timezone.now()
    agent.save(update_fields=["total_runs", "last_run_at"])
    return run


def _dispatch(request, project, agent, payload):
    """Envoi au runtime externe — à implémenter quand les agents existeront."""
    from .services import dispatch  # noqa: F401  (contrat à implémenter)

    run = AgentRun.objects.create(
        project=project, agent=agent, triggered_by=request.user,
        status=AgentRun.Status.QUEUED, step="Mise en file", input_payload=payload,
    )
    try:
        dispatch(run)
    except NotImplementedError:
        run.status = AgentRun.Status.SKIPPED
        run.step = "Runtime non implémenté"
        run.error_message = "dispatch() n'est pas implémenté — emplacement réservé."
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "step", "error_message", "finished_at"])
    return run


class ValidateProposalView(views.APIView):
    """
    Étape de validation humaine obligatoire avant toute écriture Jira/Trello.

    POST { "decision": "APPROVE" | "REJECT", "reason": "...",
           "create_tasks": true, "push_to_external": false,
           "assignments": {"<suggestion_id>": true} }
    """

    def post(self, request, pk):
        try:
            proposal = Proposal.objects.select_related("project", "run").get(pk=pk)
        except Proposal.DoesNotExist:
            return Response({"detail": "Proposition introuvable."}, status=404)

        if not _can_pilot(request.user, proposal.project):
            return Response(
                {"detail": "Réservé au chef de projet propriétaire du projet ou à un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        decision = (request.data.get("decision") or "").upper()
        reason = request.data.get("reason", "")
        create_tasks = bool(request.data.get("create_tasks", True))
        push_external = bool(request.data.get("push_to_external", False))
        assignment_choices = request.data.get("assignments") or {}

        if decision not in ("APPROVE", "REJECT"):
            return Response({"detail": "decision doit valoir APPROVE ou REJECT."}, status=400)

        if decision == "REJECT":
            proposal.status = Proposal.Status.REJECTED
            proposal.rejection_reason = reason
            proposal.validated_by = request.user
            proposal.validated_at = timezone.now()
            proposal.save()
            _notify_validation(request, proposal, False, reason)
            return Response(ProposalSerializer(proposal).data)

        # --- Décisions d'assignation (Agent 2) ---------------------------
        for sug in proposal.assignments.all():
            choice = assignment_choices.get(str(sug.id))
            if choice is not None:
                sug.accepted = bool(choice)
                sug.save(update_fields=["accepted"])

        created_tasks = 0
        if create_tasks:
            created_tasks = _materialise(request, proposal)

        proposal.status = Proposal.Status.APPROVED
        proposal.validated_by = request.user
        proposal.validated_at = timezone.now()
        proposal.save(update_fields=["status", "validated_by", "validated_at"])

        # Store the approved proposal in the RAG past-projects store
        # so future Scoping runs can retrieve it as similar context.
        try:
            from orchestration.scoping.rag import store_past_project
            brief = proposal.run.input_payload.get("brief", "") if proposal.run else ""
            if not brief:
                brief = proposal.summary or proposal.project.brief or ""
            store_past_project(brief, proposal)
        except Exception as e:
            # Non-fatal — RAG store is best-effort
            import logging
            logging.getLogger(__name__).warning("Failed to store past project for RAG: %s", e)

        pushed_tasks = 0
        push_errors: list = []
        if push_external:
            pushed_tasks, push_errors = _push_proposal_to_trello(proposal, request)

        _notify_validation(request, proposal, True, "", created_tasks)
        return Response({
            "proposal": ProposalSerializer(proposal).data,
            "created_tasks": created_tasks,
            "pushed_tasks": pushed_tasks,
            "push_errors": push_errors,
        })


class PushProposalToTrelloView(views.APIView):
    """
    Push an APPROVED proposal's tasks to Trello on demand.

    Use case: a proposal was approved WITHOUT 'push_to_external' checked
    (or before Agent 2 was activated), and the PM now wants to push the
    tasks to Trello without re-approving the proposal.

    POST /api/proposals/<pk>/push-to-trello/
    Returns: { pushed_tasks, push_errors, board_name, list_name }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            proposal = Proposal.objects.select_related("project", "run").get(pk=pk)
        except Proposal.DoesNotExist:
            return Response({"detail": "Proposition introuvable."}, status=404)

        if not _can_pilot(request.user, proposal.project):
            return Response(
                {"detail": "Réservé au chef de projet propriétaire du projet ou à un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if proposal.status != Proposal.Status.APPROVED:
            return Response(
                {"detail": f"La proposition doit être APPROVED (statut actuel: {proposal.status})."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pushed, errors = _push_proposal_to_trello(proposal, request)
        return Response({
            "pushed_tasks": pushed,
            "push_errors": errors,
        })


class AutoAssignProposalView(views.APIView):
    """
    Auto-assign the best matching candidate to each task that has no assignee.

    Use case: a proposal was approved but assignments were refused (or not
    accepted), so tasks were created without assignees. This endpoint
    re-evaluates the AssignmentSuggestions and assigns the best candidate
    (highest match_score) to each unassigned task.

    POST /api/proposals/<pk>/auto-assign/
    Returns: { assigned_count, skipped_count, errors }
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        try:
            proposal = Proposal.objects.select_related("project", "run").get(pk=pk)
        except Proposal.DoesNotExist:
            return Response({"detail": "Proposition introuvable."}, status=404)

        if not _can_pilot(request.user, proposal.project):
            return Response(
                {"detail": "Réservé au chef de projet propriétaire du projet ou à un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )

        from projects.models import Task as _Task

        project = proposal.project
        assigned = 0
        skipped = 0
        errors: list = []

        # Build a map: task_title → best AssignmentSuggestion (highest match_score)
        suggestions_by_task = {}
        for sug in proposal.assignments.all().select_related("candidate").order_by("-match_score"):
            key = (sug.task_title or "").strip().lower()
            if key and key not in suggestions_by_task:
                suggestions_by_task[key] = sug
            # Also key by task_ref if available
            if sug.task_ref:
                ref_key = sug.task_ref.strip().lower()
                if ref_key not in suggestions_by_task:
                    suggestions_by_task[ref_key] = sug

        # Also key by task_ref from the proposal payload
        for t in proposal.tasks_payload or []:
            title = (t.get("title") or "").strip()
            ref = (t.get("ref") or "").strip()
            if ref and ref.lower() in suggestions_by_task:
                suggestions_by_task[title.lower()] = suggestions_by_task[ref.lower()]
            if title and title.lower() in suggestions_by_task:
                suggestions_by_task[ref.lower()] = suggestions_by_task[title.lower()]

        # For each task with no assignee, find the best candidate
        unassigned_tasks = _Task.objects.filter(
            project=project,
            assignee__isnull=True,
        ).order_by("id")

        for task in unassigned_tasks:
            title_key = (task.title or "").strip().lower()
            sug = suggestions_by_task.get(title_key)
            if sug and sug.candidate:
                try:
                    task.assignee = sug.candidate
                    task.save(update_fields=["assignee"])
                    # Mark suggestion as accepted
                    if sug.accepted is not True:
                        sug.accepted = True
                        sug.save(update_fields=["accepted"])
                    assigned += 1
                except Exception as e:
                    errors.append(f"Tâche '{task.title[:40]}': {e}")
            else:
                skipped += 1

        # Audit log
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.AGENT_WRITE,
            severity=AuditLog.Severity.NOTICE if not errors else AuditLog.Severity.WARNING,
            entity_type="Proposal", entity_id=str(proposal.pk),
            entity_label=proposal.title,
            description=(
                f"Auto-assignation : {assigned} tâche(s) assignée(s) "
                f"({skipped} sans suggestion matchée)"
                f"{f', {len(errors)} erreur(s)' if errors else ''}."
            ),
            agent_key="OPS", run=proposal.run, ip_address=_client_ip(request),
            metadata={
                "assigned_count": assigned,
                "skipped_count": skipped,
                "errors": errors[:5],
            },
        )

        # Notification
        Notification.objects.create(
            user=request.user,
            category=Notification.Category.AGENT,
            level=Notification.Level.AGENT,
            title=f"Auto-assignation terminée — {project.name}",
            message=(
                f"{assigned} tâche(s) assignée(s) automatiquement. "
                f"{skipped} tâche(s) sans suggestion matchée."
            ),
            link=f"/app/projects/{project.pk}/tasks",
            entity_type="Proposal",
            entity_id=proposal.pk,
            metadata={"assigned_count": assigned, "skipped_count": skipped},
        )

        return Response({
            "assigned_count": assigned,
            "skipped_count": skipped,
            "errors": errors,
        })


def _materialise(request, proposal):
    """Transforme les tâches proposées en vraies tâches du projet."""
    from datetime import date, timedelta

    project = proposal.project
    created = 0
    wp_by_name = {}

    for idx, lot in enumerate(proposal.lots_payload or []):
        wp, _ = WorkPackage.objects.get_or_create(
            project=project,
            name=lot.get("name", f"Lot {idx + 1}"),
            defaults={
                "description": lot.get("description", ""),
                "order": lot.get("order", idx),
                "color": lot.get("color") or _palette(idx),
                "estimated_effort_hours": lot.get("estimate_hours", 0) or 0,
                "confidence": lot.get("confidence", 0) or 0,
            },
        )
        wp_by_name[wp.name] = wp

    # NEW: Auto-create sprints from sprints_payload with calculated start/end dates
    # Each sprint is 2 weeks long, starting from project.start_date (or today)
    sprint_start = project.start_date or date.today()
    sprint_duration_weeks = 2
    for idx, sp in enumerate(proposal.sprints_payload or []):
        sprint_name = sp.get("name") or f"Sprint {idx + 1}"
        start = sprint_start + timedelta(weeks=idx * sprint_duration_weeks)
        end = start + timedelta(weeks=sprint_duration_weeks) - timedelta(days=1)
        Sprint.objects.get_or_create(
            project=project,
            name=sprint_name,
            defaults={
                "goal": sp.get("goal", ""),
                "order": idx + 1,
                "status": Sprint.Status.PLANNED,
                "start_date": start,
                "end_date": end,
                "capacity_hours": sp.get("capacity_hours", 0) or 0,
            },
        )

    sprint_by_name = {s.name: s for s in project.sprints.all()}

    # Build lookup maps for accepted assignments — by ref AND by title (robust matching)
    accepted_by_ref: dict[str, AssignmentSuggestion] = {}
    accepted_by_title: dict[str, AssignmentSuggestion] = {}
    for a in proposal.assignments.filter(accepted=True).select_related("candidate"):
        if a.task_ref:
            accepted_by_ref[a.task_ref.strip()] = a
            accepted_by_ref[a.task_ref.strip().lower()] = a
        if a.task_title:
            accepted_by_title[a.task_title.strip()] = a
            accepted_by_title[a.task_title.strip().lower()] = a

    for idx, t in enumerate(proposal.tasks_payload or []):
        title = t.get("title") or f"Tâche {idx + 1}"
        wp = wp_by_name.get(t.get("lot") or t.get("work_package"))
        # Robust matching: try ref first (exact + lowercase), then title (exact + lowercase)
        sug = None
        ref = (t.get("ref") or "").strip()
        if ref:
            sug = accepted_by_ref.get(ref) or accepted_by_ref.get(ref.lower())
        if not sug and title:
            sug = accepted_by_title.get(title.strip()) or accepted_by_title.get(title.strip().lower())

        # Determine sprint for this task + due date = sprint end date
        sprint_name = t.get("sprint") or ""
        task_sprint = sprint_by_name.get(sprint_name)
        due_date = task_sprint.end_date if task_sprint else None

        # Check if task already exists (from a previous proposal approval)
        existing = Task.objects.filter(project=project, title=title).first()
        if existing:
            # Update assignee, sprint, and due_date on existing task if missing
            update_fields = []
            if sug and sug.candidate and not existing.assignee:
                existing.assignee = sug.candidate
                update_fields.append("assignee")
            if not existing.sprint and task_sprint:
                existing.sprint = task_sprint
                update_fields.append("sprint")
            if not existing.due_date and due_date:
                existing.due_date = due_date
                update_fields.append("due_date")
            if update_fields:
                existing.save(update_fields=update_fields)
            continue

        Task.objects.create(
            project=project,
            work_package=wp,
            sprint=task_sprint,
            title=title,
            description=t.get("description", ""),
            task_type=t.get("type", "FEATURE") if t.get("type") in dict(Task.Type.choices) else "FEATURE",
            priority=(t.get("priority") or "MEDIUM").upper()
            if (t.get("priority") or "MEDIUM").upper() in dict(Task.Priority.choices) else "MEDIUM",
            status="TODO",
            assignee=sug.candidate if sug else None,
            estimate_hours=t.get("estimate_hours", 0) or 0,
            story_points=t.get("story_points", 0) or 0,
            required_skills=t.get("skills", []),
            acceptance_criteria=t.get("acceptance_criteria", []),
            risk_score=t.get("risk_score", 0) or 0,
            labels=t.get("labels", []),
            created_by_agent=True,
            due_date=due_date,
        )
        created += 1

    if created:
        project.estimated_effort_hours = sum(
            float(t.estimate_hours) for t in project.tasks.all()
        )
        project.save(update_fields=["estimated_effort_hours"])
    return created


def _palette(i):
    palette = ["#2563EB", "#0EA5E9", "#1D4ED8", "#0284C7", "#3B82F6", "#0369A1"]
    return palette[i % len(palette)]


def _notify_validation(request, proposal, approved, reason="", created_tasks=0):
    level = Notification.Level.SUCCESS if approved else Notification.Level.WARNING
    title = "Plan validé ✅" if approved else "Plan rejeté"
    msg = (
        f"Le plan « {proposal.title} » a été validé : {created_tasks} tâche(s) créée(s) sur « {proposal.project.name} »."
        if approved else
        f"Le plan « {proposal.title} » a été rejeté. {reason}".strip()
    )
    Notification.objects.create(
        user=request.user, category=Notification.Category.VALIDATION, level=level,
        title=title, message=msg, link=f"/app/projects/{proposal.project_id}/validation",
        entity_type="Proposal", entity_id=proposal.pk,
        metadata={"created_tasks": created_tasks, "approved": approved},
    )
    AuditLog.objects.create(
        actor=request.user,
        action=AuditLog.Action.VALIDATE if approved else AuditLog.Action.REJECT,
        severity=AuditLog.Severity.NOTICE if approved else AuditLog.Severity.WARNING,
        entity_type="Proposal", entity_id=str(proposal.pk), entity_label=proposal.title,
        description=msg, agent_key="SCOPING", run=proposal.run, ip_address=_client_ip(request),
    )


class AgentMonitorView(views.APIView):
    """Tableau de bord de supervision des agents (style Grafana, côté API)."""

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)
        qs = AgentRun.objects.filter(created_at__gte=since)

        per_agent = list(
            qs.values("agent__key", "agent__name", "agent__short_name", "agent__color")
            .annotate(
                total=Count("id"),
                succeeded=Count("id", filter=Q(status=AgentRun.Status.SUCCEEDED)),
                failed=Count("id", filter=Q(status=AgentRun.Status.FAILED)),
                skipped=Count("id", filter=Q(status=AgentRun.Status.SKIPPED)),
                awaiting=Count("id", filter=Q(status=AgentRun.Status.AWAITING_VALIDATION)),
                avg_latency=Avg("latency_ms"),
            )
            .order_by("agent__order")
        )
        for row in per_agent:
            row["success_rate"] = round(row["succeeded"] / row["total"] * 100, 1) if row["total"] else 0
            row["avg_latency"] = round(row["avg_latency"] or 0)

        # Série temporelle quotidienne
        from django.db.models.functions import TruncDate
        timeline_qs = (
            qs.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(total=Count("id"),
                      failed=Count("id", filter=Q(status=AgentRun.Status.FAILED)),
                      skipped=Count("id", filter=Q(status=AgentRun.Status.SKIPPED)))
            .order_by("day")
        )
        timeline = [
            {"date": r["day"].isoformat(), "total": r["total"], "failed": r["failed"], "skipped": r["skipped"]}
            for r in timeline_qs
        ]

        return Response({
            "enabled": settings.AGENT_RUNTIME["ENABLED"],
            "orchestrator": settings.AGENT_RUNTIME["ORCHESTRATOR"],
            "window_days": days,
            "totals": {
                "runs": qs.count(),
                "success": qs.filter(status=AgentRun.Status.SUCCEEDED).count(),
                "failed": qs.filter(status=AgentRun.Status.FAILED).count(),
                "skipped": qs.filter(status=AgentRun.Status.SKIPPED).count(),
                "awaiting_validation": qs.filter(status=AgentRun.Status.AWAITING_VALIDATION).count(),
                "avg_latency_ms": round(qs.aggregate(a=Avg("latency_ms"))["a"] or 0),
            },
            "per_agent": per_agent,
            "timeline": timeline,
            "json_error_rate": round(
                qs.filter(status=AgentRun.Status.FAILED).count() / qs.count() * 100, 1
            ) if qs.count() else 0,
        })


class AssignmentSuggestionViewSet(ModelViewSet):
    serializer_class = AssignmentSuggestionSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = AssignmentSuggestion.objects.select_related("candidate", "proposal")
        proposal = self.request.query_params.get("proposal")
        if proposal:
            qs = qs.filter(proposal_id=proposal)
        return qs

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        sug = self.get_object()
        sug.accepted = bool(request.data.get("accepted", True))
        sug.save(update_fields=["accepted"])
        return Response(self.get_serializer(sug).data)


# ===========================================================================
# Agent 2 — push to Trello (COMPREHENSIVE VERSION)
# Features:
#   - One Trello list per sprint (instead of one big list)
#   - Priority color labels (red/yellow/green)
#   - Due dates from task.due_date
#   - Assignees matched by email (Cadria user → Trello board member)
#   - Acceptance criteria as a native Trello checklist
#   - Rich card description (lot, sprint, estimate, priority, skills, risk)
#   - "Cadria" marker label on every card
# ===========================================================================

# Priority → Trello label color mapping
PRIORITY_COLOR = {
    "LOWEST":  "green",
    "LOW":     "green",
    "MEDIUM":  "yellow",
    "HIGH":    "red",
    "HIGHEST": "red",
}

PRIORITY_LABEL_FR = {
    "LOWEST":  "Très basse",
    "LOW":     "Basse",
    "MEDIUM":  "Moyenne",
    "HIGH":    "Haute",
    "HIGHEST": "Critique",
}


def _push_proposal_to_trello(proposal, request):
    """Push approved tasks to Trello with rich metadata.

    Returns (pushed_count, errors).
    """
    from django.conf import settings as _settings
    from orchestration.ops.trello_client import TrelloClient, TrelloError
    from projects.models import Integration, Task as _Task

    project = proposal.project
    errors: list = []
    pushed = 0

    # 1. Find the Trello integration
    try:
        integration = Integration.objects.get(project=project, provider="TRELLO")
    except Integration.DoesNotExist:
        msg = "Aucune intégration Trello connectée à ce projet — ouvrez l'onglet Connecteurs d'abord."
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.AGENT_WRITE,
            severity=AuditLog.Severity.WARNING,
            entity_type="Proposal", entity_id=str(proposal.pk),
            entity_label=proposal.title,
            description=f"Push Trello annulé : {msg}",
            agent_key="OPS", run=proposal.run, ip_address=_client_ip(request),
        )
        return 0, [msg]

    if integration.status != "CONNECTED":
        return 0, [f"L'intégration Trello n'est pas connectée (statut: {integration.status})."]

    api_key = getattr(_settings, "TRELLO_APP_KEY", "")
    if not api_key:
        return 0, ["TRELLO_APP_KEY manquant dans backend/.env"]

    token = integration.workspace
    board_id = integration.board_key
    if not token or not board_id:
        return 0, ["Identifiants Trello incomplets (token ou board_id manquant)."]

    client = TrelloClient(api_key=api_key, api_token=token)

    # 2. Fetch board members (one API call — cached for the whole push)
    #    Used for email-based assignee matching.
    board_members = client.get_board_members(board_id)
    members_by_email = {}
    members_by_name = {}
    for m in board_members:
        if m.get("email"):
            members_by_email[m["email"].lower()] = m
        if m.get("fullName"):
            members_by_name[m["fullName"].lower()] = m
    unmatched_assignees: list[str] = []

    # 3. Build sprint lists (one Trello list per sprint)
    #    Tasks without a sprint go to a fallback list named after the project.
    sprints = list(project.sprints.all().order_by("name")) if hasattr(project, "sprints") else []
    sprint_list_ids: dict[str, str] = {}  # sprint_name → Trello list_id

    # Try to find existing lists first (avoid duplicates on re-push)
    try:
        existing_lists = client._get(
            f"/1/boards/{board_id}/lists",
            params={"fields": "name,id"},
        )
        existing_by_name = {lst.get("name"): lst.get("id") for lst in (existing_lists or [])}
    except Exception:
        existing_by_name = {}

    if sprints:
        for sprint in sprints:
            list_name = (sprint.name or f"Sprint {sprint.id}")[:50]
            if list_name in existing_by_name:
                sprint_list_ids[sprint.name] = existing_by_name[list_name]
            else:
                try:
                    result = client.create_list(board_id, list_name)
                    sprint_list_ids[sprint.name] = result["external_id"]
                except TrelloError as e:
                    errors.append(f"Liste '{list_name}': {e}")
    else:
        # No sprints → use project name as the fallback list
        list_name = (project.name or "Cadria")[:50]
        if list_name in existing_by_name:
            sprint_list_ids["__default__"] = existing_by_name[list_name]
        else:
            try:
                result = client.create_list(board_id, list_name)
                sprint_list_ids["__default__"] = result["external_id"]
            except TrelloError as e:
                errors.append(f"Liste '{list_name}': {e}")
                return 0, errors

    default_list_id = next(iter(sprint_list_ids.values()), "")
    if not default_list_id:
        return 0, ["Impossible de créer ou trouver une liste Trello pour le projet."]

    # 4. Get tasks to push
    tasks_to_push = _Task.objects.filter(
        project=project,
        created_by_agent=True,
        external_id="",
    ).select_related("work_package", "sprint", "assignee").order_by("id")

    if not tasks_to_push:
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.AGENT_WRITE,
            severity=AuditLog.Severity.NOTICE,
            entity_type="Proposal", entity_id=str(proposal.pk),
            entity_label=proposal.title,
            description="Aucune tâche à pousser vers Trello (déjà synchronisées).",
            agent_key="OPS", run=proposal.run, ip_address=_client_ip(request),
        )
        return 0, []

    # 5. Push each task
    for task in tasks_to_push:
        try:
            # --- Pick the right list for this task ---
            list_id = None
            if task.sprint and task.sprint.name in sprint_list_ids:
                list_id = sprint_list_ids[task.sprint.name]
            elif "__default__" in sprint_list_ids:
                list_id = sprint_list_ids["__default__"]
            else:
                list_id = default_list_id

            # --- Build rich description ---
            desc_lines: list[str] = []
            if task.description:
                desc_lines.append(task.description[:1200])
                desc_lines.append("")
            if task.work_package:
                desc_lines.append(f"📦 Lot: {task.work_package.name}")
            if task.sprint:
                desc_lines.append(f"🏃 Sprint: {task.sprint.name}")
            if task.estimate_hours:
                desc_lines.append(f"⏱ Estimé: {task.estimate_hours}h")
            if task.spent_hours:
                desc_lines.append(f"✅ Réalisé: {task.spent_hours}h")
            prio_fr = PRIORITY_LABEL_FR.get(task.priority, task.priority)
            desc_lines.append(f"🔴 Priorité: {prio_fr}")
            if task.risk_score:
                desc_lines.append(f"⚠️ Score de risque: {task.risk_score}/100")
            if task.due_date:
                desc_lines.append(f"📅 Échéance: {task.due_date.strftime('%d/%m/%Y')}")
            desc_lines.append(f"🔗 Cadria task ID: {task.id}")
            if getattr(task, "required_skills", None):
                skills = task.required_skills if isinstance(task.required_skills, list) else []
                if skills:
                    desc_lines.append("")
                    desc_lines.append("🛠 Compétences requises: " + ", ".join(skills[:8]))
            description = "\n".join(desc_lines)[:2000]

            # --- Create the card ---
            card_title = task.title[:150]
            result = client.create_card(list_id, card_title, description)
            card_id = result["external_id"]
            task.external_id = card_id
            task.external_url = result["external_url"]
            task.save(update_fields=["external_id", "external_url"])
            pushed += 1

            # --- Add priority color label ---
            color = PRIORITY_COLOR.get(task.priority, "purple")
            client.add_label_to_card(card_id, color)

            # --- Add "Cadria" marker label (blue) ---
            client.add_named_label_to_card(card_id, "blue", "Cadria")

            # --- Set due date if present ---
            if task.due_date:
                # Trello expects ISO 8601 with time
                due_iso = task.due_date.strftime("%Y-%m-%dT23:59:59.000Z")
                client.set_card_due_date(card_id, due_iso)

            # --- Assign member (match by email, then by full name) ---
            if task.assignee:
                assignee = task.assignee
                member = None
                # Try email match first
                if getattr(assignee, "email", None):
                    member = members_by_email.get(assignee.email.lower())
                # Fall back to full name match
                if not member and getattr(assignee, "full_name", None):
                    member = members_by_name.get(assignee.full_name.lower())
                if member:
                    client.add_member_to_card(card_id, member["id"])
                else:
                    name = getattr(assignee, "full_name", None) or getattr(assignee, "email", "?")
                    unmatched_assignees.append(f"{name} (task #{task.id})")

            # --- Create acceptance criteria checklist ---
            criteria = getattr(task, "acceptance_criteria", None) or []
            if isinstance(criteria, list) and criteria:
                client.create_checklist(card_id, "Critères d'acceptation", criteria)

        except TrelloError as e:
            errors.append(f"Tâche '{task.title[:40]}': {e}")
        except Exception as e:
            errors.append(f"Erreur interne sur '{task.title[:40]}': {e}")

    # 6. Update integration last_sync_at
    integration.last_sync_at = timezone.now()
    if errors:
        integration.last_error = "; ".join(errors[:3])
    else:
        integration.last_error = ""
    integration.save(update_fields=["last_sync_at", "last_error"])

    # 7. Audit log
    unmatched_note = ""
    if unmatched_assignees:
        unmatched_note = f" · {len(unmatched_assignees)} assignation(s) non matchées (email différent entre Cadria et Trello)"

    AuditLog.objects.create(
        actor=request.user, action=AuditLog.Action.AGENT_WRITE,
        severity=AuditLog.Severity.NOTICE if not errors else AuditLog.Severity.WARNING,
        entity_type="Proposal", entity_id=str(proposal.pk),
        entity_label=proposal.title,
        description=(
            f"Agent 2 — push Trello : {pushed} tâche(s) poussée(s) "
            f"vers le board '{integration.name}'"
            f"{unmatched_note}"
            f"{f', {len(errors)} erreur(s)' if errors else ''}."
        ),
        agent_key="OPS", run=proposal.run, ip_address=_client_ip(request),
        metadata={
            "board_id": board_id,
            "sprint_lists": list(sprint_list_ids.keys()),
            "pushed_count": pushed,
            "errors": errors[:5],
            "unmatched_assignees": unmatched_assignees[:10],
        },
    )

    # 8. Notification
    Notification.objects.create(
        user=request.user,
        category=Notification.Category.AGENT,
        level=Notification.Level.AGENT,
        title=f"Tâches poussées vers Trello — {project.name}",
        message=(
            f"{pushed} tâche(s) créée(s) sur le board Trello '{integration.name}', "
            f"réparties dans {len(sprint_list_ids)} liste(s)."
            + (f" {len(errors)} erreur(s)." if errors else "")
            + (f" {len(unmatched_assignees)} assignation(s) non matchées." if unmatched_assignees else "")
        ),
        link=f"/app/projects/{project.pk}/tasks",
        entity_type="Proposal",
        entity_id=proposal.pk,
        metadata={"agent": "OPS", "pushed_count": pushed, "errors": errors[:5]},
    )

    return pushed, errors
