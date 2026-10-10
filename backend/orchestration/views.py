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
from projects.models import Project, Task, WorkPackage


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

        if push_external:
            AuditLog.objects.create(
                actor=request.user, action=AuditLog.Action.AGENT_WRITE,
                severity=AuditLog.Severity.WARNING,
                entity_type="Proposal", entity_id=str(proposal.pk),
                entity_label=proposal.title,
                description=(
                    f"Demande de poussée vers {proposal.project.external_provider or 'Jira/Trello'} — "
                    "Agent 2 non branché, aucune écriture effectuée."
                ),
                agent_key="OPS", run=proposal.run, ip_address=_client_ip(request),
            )

        _notify_validation(request, proposal, True, "", created_tasks)
        return Response({"proposal": ProposalSerializer(proposal).data, "created_tasks": created_tasks})


def _materialise(request, proposal):
    """Transforme les tâches proposées en vraies tâches du projet."""
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

    sprint_by_name = {s.name: s for s in project.sprints.all()}

    accepted_by_task = {
        a.task_ref: a for a in proposal.assignments.filter(accepted=True).select_related("candidate")
    }

    for idx, t in enumerate(proposal.tasks_payload or []):
        title = t.get("title") or f"Tâche {idx + 1}"
        if Task.objects.filter(project=project, title=title).exists():
            continue
        wp = wp_by_name.get(t.get("lot") or t.get("work_package"))
        sug = accepted_by_task.get(t.get("ref") or title)
        Task.objects.create(
            project=project,
            work_package=wp,
            sprint=sprint_by_name.get(t.get("sprint") or ""),
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
