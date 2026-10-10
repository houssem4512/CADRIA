from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from audit.models import AuditLog
from notifications.models import Notification

from .models import Comment, Integration, Project, RiskAlert, Sprint, Task, WorkPackage
from .serializers import (
    CommentSerializer,
    IntegrationSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    ProjectWriteSerializer,
    RiskAlertSerializer,
    SprintSerializer,
    TaskSerializer,
    TaskWriteSerializer,
    WorkPackageSerializer,
)

User = get_user_model()


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")


def _visible_projects(user):
    qs = Project.objects.select_related("owner", "team").prefetch_related("members")
    if user.is_superuser or user.role == User.Role.ADMIN:
        return qs.all()
    return qs.filter(Q(owner=user) | Q(members=user)).distinct()


class IsOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        u = request.user
        if u.is_superuser or u.role == User.Role.ADMIN:
            return True
        owner = getattr(obj, "owner", None)
        return owner == u or (hasattr(obj, "members") and obj.members.filter(pk=u.pk).exists())


class IsPMOrAdmin(permissions.BasePermission):
    """La création de projets est réservée aux chefs de projet et aux administrateurs."""

    message = "Seul un chef de projet ou un administrateur peut créer un projet."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated
                    and (u.is_superuser or u.role in (User.Role.ADMIN, User.Role.PM)))


class ProjectViewSet(ModelViewSet):
    search_fields = ["name", "reference", "summary", "tags"]
    ordering_fields = ["created_at", "name", "progress", "risk_score", "target_end_date"]

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated(), IsPMOrAdmin()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProjectWriteSerializer
        return ProjectDetailSerializer if self.action == "retrieve" else ProjectListSerializer

    def get_queryset(self):
        qs = _visible_projects(self.request.user)
        status_ = self.request.query_params.get("status")
        health = self.request.query_params.get("health")
        mine = self.request.query_params.get("mine")
        if status_:
            qs = qs.filter(status=status_)
        if health:
            qs = qs.filter(health=health)
        if mine == "true":
            qs = qs.filter(owner=self.request.user)
        return qs

    def create(self, request, *args, **kwargs):
        """Crée le projet puis renvoie sa représentation détaillée (référence incluse)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        project = Project.objects.get(pk=serializer.instance.pk)
        detail = ProjectDetailSerializer(project, context={"request": request})
        return Response(detail.data, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        project = serializer.save(owner=self.request.user)
        project.members.add(self.request.user)
        AuditLog.objects.create(
            actor=self.request.user, action=AuditLog.Action.CREATE,
            entity_type="Project", entity_id=str(project.pk), entity_label=project.name,
            description=f"Projet « {project.name} » créé", severity=AuditLog.Severity.NOTICE,
            ip_address=_client_ip(self.request),
        )
        Notification.objects.create(
            user=self.request.user, category=Notification.Category.SYSTEM,
            level=Notification.Level.SUCCESS,
            title="Projet créé",
            message=f"« {project.name} » est prêt. Lancez l'Agent 1 pour obtenir un découpage.",
            link=f"/app/projects/{project.pk}/agents",
            entity_type="Project", entity_id=project.pk,
        )

    def perform_update(self, serializer):
        project = serializer.save()
        AuditLog.objects.create(
            actor=self.request.user, action=AuditLog.Action.UPDATE,
            entity_type="Project", entity_id=str(project.pk), entity_label=project.name,
            description=f"Projet « {project.name} » modifié", ip_address=_client_ip(self.request),
            metadata={"fields": list(serializer.validated_data.keys())},
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            actor=self.request.user, action=AuditLog.Action.DELETE,
            entity_type="Project", entity_id=str(instance.pk), entity_label=instance.name,
            description=f"Projet « {instance.name} » supprimé", severity=AuditLog.Severity.WARNING,
            ip_address=_client_ip(self.request),
        )
        instance.delete()

    # --- Actions métier ---------------------------------------------------
    @action(detail=True, methods=["get"])
    def board(self, request, pk=None):
        """Kanban : tâches groupées par statut."""
        project = self.get_object()
        tasks = project.tasks.select_related("assignee", "work_package", "sprint").order_by("priority", "title")
        columns = [
            {"key": s.value, "label": s.label, "tasks": TaskSerializer([t for t in tasks if t.status == s.value], many=True).data}
            for s in Task.Status
        ]
        return Response({"project": ProjectListSerializer(project).data, "columns": columns})

    @action(detail=True, methods=["get"])
    def workload(self, request, pk=None):
        """Charge par membre — alimente l'équilibrage de l'Agent 2."""
        project = self.get_object()
        rows = []
        for member in project.members.all():
            agg = member.assigned_tasks.filter(project=project).exclude(status="DONE").aggregate(
                n=Count("id"), est=Sum("estimate_hours"), spent=Sum("spent_hours")
            )
            capacity = float(member.weekly_capacity_hours or 0)
            est = float(agg["est"] or 0)
            rows.append({
                "id": member.id, "name": member.full_name, "initials": member.initials,
                "color": member.avatar_color, "job_title": member.job_title,
                "open_tasks": agg["n"], "estimated_hours": est,
                "spent_hours": float(agg["spent"] or 0), "capacity_hours": capacity,
                "utilisation_pct": round(est / capacity * 100, 1) if capacity else 0,
                "skills": [us.skill.name for us in member.skills.all()],
            })
        return Response(rows)

    @action(detail=True, methods=["post"])
    def recompute(self, request, pk=None):
        """Recalcule progression, charge et score de risque agrégé."""
        project = self.get_object()
        tasks = project.tasks.all()
        total, done = tasks.count(), tasks.filter(status="DONE").count()
        project.progress = round(done / total * 100) if total else 0
        project.estimated_effort_hours = sum(float(t.estimate_hours) for t in tasks)
        project.spent_effort_hours = sum(float(t.spent_hours) for t in tasks)
        open_alerts = project.risk_alerts.filter(acknowledged=False)
        crit = open_alerts.filter(severity=RiskAlert.Severity.CRITICAL).count()
        warn = open_alerts.filter(severity=RiskAlert.Severity.WARNING).count()
        overdue = sum(1 for t in tasks if t.is_overdue)
        blocked = tasks.filter(blocked=True).exclude(status="DONE").count()
        score = min(100, crit * 22 + warn * 9 + overdue * 4 + blocked * 6)
        project.risk_score = score
        project.health = (Project.Health.RED if score >= 55
                          else Project.Health.AMBER if score >= 25 else Project.Health.GREEN)
        if project.health == Project.Health.RED and project.status not in (
            Project.Status.COMPLETED, Project.Status.CANCELLED
        ):
            project.status = Project.Status.AT_RISK
        project.save()
        return Response(ProjectDetailSerializer(project, context={"request": request}).data)

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        """Synchronisation Jira/Trello — délégation à l'Agent 2 (non branché)."""
        project = self.get_object()
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.SYNC, entity_type="Project",
            entity_id=str(project.pk), entity_label=project.name,
            description=f"Synchronisation {project.external_provider or 'Jira/Trello'} demandée — Agent 2 non branché",
            agent_key="OPS", severity=AuditLog.Severity.NOTICE, ip_address=_client_ip(request),
        )
        Notification.objects.create(
            user=request.user, category=Notification.Category.INTEGRATION,
            level=Notification.Level.AGENT, title="Synchronisation en attente",
            message=f"Aucun connecteur {project.external_provider or 'Jira/Trello'} actif pour « {project.name} ».",
            link=f"/app/projects/{project.pk}/integrations",
            entity_type="Project", entity_id=project.pk,
        )
        return Response({"detail": "Synchronisation demandée (connecteur non branché)."}, status=202)


class WorkPackageViewSet(ModelViewSet):
    serializer_class = WorkPackageSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = WorkPackage.objects.select_related("project")
        project = self.request.query_params.get("project")
        if project:
            qs = qs.filter(project_id=project)
        return qs


class SprintViewSet(ModelViewSet):
    serializer_class = SprintSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = Sprint.objects.all()
        project = self.request.query_params.get("project")
        if project:
            qs = qs.filter(project_id=project)
        return qs.order_by("order", "id")


class TaskViewSet(ModelViewSet):
    filterset_backends = []
    search_fields = ["title", "description"]

    def get_serializer_class(self):
        return TaskWriteSerializer if self.action in ("create", "update", "partial_update") else TaskSerializer

    def get_queryset(self):
        qs = Task.objects.select_related("assignee", "project", "work_package", "sprint").all()
        project = self.request.query_params.get("project")
        assignee = self.request.query_params.get("assignee")
        stat = self.request.query_params.get("status")
        sprint = self.request.query_params.get("sprint")
        risk = self.request.query_params.get("at_risk")
        mine = self.request.query_params.get("mine")
        if project:
            qs = qs.filter(project_id=project)
        if assignee:
            qs = qs.filter(assignee_id=assignee)
        if mine == "true":
            qs = qs.filter(assignee=self.request.user)
        if stat:
            qs = qs.filter(status=stat)
        if sprint:
            qs = qs.filter(sprint_id=sprint)
        if risk == "true":
            qs = qs.filter(risk_score__gte=50)
        return qs.order_by("-priority", "-risk_score", "title")

    def perform_create(self, serializer):
        task = serializer.save()
        _task_notification(task, self.request.user, created=True)
        AuditLog.objects.create(
            actor=self.request.user, action=AuditLog.Action.CREATE, entity_type="Task",
            entity_id=str(task.pk), entity_label=task.title, description="Tâche créée",
            ip_address=_client_ip(self.request),
        )

    def perform_update(self, serializer):
        before_status = serializer.instance.status
        before_assignee = serializer.instance.assignee_id
        task = serializer.save()
        if before_status != task.status:
            AuditLog.objects.create(
                actor=self.request.user, action=AuditLog.Action.UPDATE, entity_type="Task",
                entity_id=str(task.pk), entity_label=task.title,
                description=f"Statut : {before_status} → {task.status}", ip_address=_client_ip(self.request),
            )
        if before_assignee != task.assignee_id:
            _task_notification(task, self.request.user)

    @action(detail=True, methods=["post"])
    def move(self, request, pk=None):
        """Glisser-déposer Kanban."""
        task = self.get_object()
        new_status = request.data.get("status")
        if new_status not in dict(Task.Status.choices):
            return Response({"detail": "Statut invalide."}, status=400)
        task.status = new_status
        task.blocked = new_status == Task.Status.BLOCKED
        task.save(update_fields=["status", "blocked"])
        return Response(TaskSerializer(task).data)

    @action(detail=False, methods=["post"])
    def bulk_status(self, request):
        ids = request.data.get("ids", [])
        new_status = request.data.get("status")
        qs = Task.objects.filter(pk__in=ids)
        count = qs.update(status=new_status, blocked=(new_status == Task.Status.BLOCKED))
        return Response({"updated": count})


def _task_notification(task, actor, created=False):
    if not task.assignee or task.assignee_id == actor.id:
        return
    Notification.objects.create(
        user=task.assignee,
        category=Notification.Category.TASK,
        level=Notification.Level.INFO,
        title="Nouvelle tâche assignée" if created else "Tâche réassignée",
        message=f"« {task.title} » — {task.project.name}",
        link=f"/app/projects/{task.project_id}/tasks",
        entity_type="Task", entity_id=task.pk,
    )


class RiskAlertViewSet(ModelViewSet):
    serializer_class = RiskAlertSerializer
    filterset_backends = []
    search_fields = ["title", "message"]

    def get_queryset(self):
        qs = RiskAlert.objects.select_related("project", "task", "sprint").all()
        project = self.request.query_params.get("project")
        severity = self.request.query_params.get("severity")
        if project:
            qs = qs.filter(project_id=project)
        if severity:
            qs = qs.filter(severity=severity)
        if self.request.query_params.get("open") == "true":
            qs = qs.filter(acknowledged=False)
        return qs

    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.acknowledged = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["acknowledged", "acknowledged_by", "acknowledged_at"])
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.ALERT, entity_type="RiskAlert",
            entity_id=str(alert.pk), entity_label=alert.title, description="Alerte accusée réception",
            ip_address=_client_ip(request),
        )
        return Response(RiskAlertSerializer(alert).data)


class CommentViewSet(ModelViewSet):
    serializer_class = CommentSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = Comment.objects.select_related("author").all()
        project = self.request.query_params.get("project")
        task = self.request.query_params.get("task")
        if project:
            qs = qs.filter(project_id=project)
        if task:
            qs = qs.filter(task_id=task)
        return qs

    def perform_create(self, serializer):
        body = serializer.validated_data.get("body", "")
        weak = any(k in body.lower() for k in ("bloqué", "bloque", "en attente", "régression",
                                               "regression", "blocker", "impossible", "depend"))
        serializer.save(
            author=self.request.user,
            weak_signal=weak,
            sentiment="NEGATIVE" if weak else "NEUTRAL",
        )


class IntegrationViewSet(ModelViewSet):
    serializer_class = IntegrationSerializer
    filterset_backends = []

    def get_queryset(self):
        qs = Integration.objects.all()
        if not (self.request.user.is_superuser or self.request.user.role == User.Role.ADMIN):
            qs = qs.filter(owner=self.request.user)
        project = self.request.query_params.get("project")
        if project:
            qs = qs.filter(project_id=project)
        return qs

    def perform_create(self, serializer):
        integration = serializer.save(owner=self.request.user)
        AuditLog.objects.create(
            actor=self.request.user, action=AuditLog.Action.CREATE, entity_type="Integration",
            entity_id=str(integration.pk), entity_label=f"{integration.provider} · {integration.name}",
            description="Connecteur ajouté", ip_address=_client_ip(self.request),
        )

    @action(detail=True, methods=["post"])
    def test(self, request, pk=None):
        """Test de connexion — nécessite l'Agent 2 ; renvoie un état simulé."""
        integration = self.get_object()
        integration.status = Integration.Status.ERROR
        integration.last_error = "Agent 2 (intégration) non branché — test indisponible."
        integration.save(update_fields=["status", "last_error"])
        return Response(IntegrationSerializer(integration).data)
