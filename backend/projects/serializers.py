from rest_framework import serializers

from accounts.models import User
from accounts.serializers import UserListSerializer
from orchestration.serializers import AgentRunSerializer

from .models import Comment, Integration, Project, RiskAlert, Sprint, Task, WorkPackage


class WorkPackageSerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(read_only=True)
    progress = serializers.SerializerMethodField()

    class Meta:
        model = WorkPackage
        fields = ["id", "project", "name", "description", "order", "color",
                  "estimated_effort_hours", "confidence", "external_id", "task_count",
                  "progress", "created_at"]
        read_only_fields = ["id", "created_at"]

    def get_progress(self, obj):
        total = obj.tasks.count()
        if not total:
            return 0
        return round(obj.tasks.filter(status="DONE").count() / total * 100)


class SprintSerializer(serializers.ModelSerializer):
    velocity = serializers.FloatField(read_only=True)
    task_count = serializers.SerializerMethodField()

    class Meta:
        model = Sprint
        fields = ["id", "project", "name", "goal", "order", "status", "start_date", "end_date",
                  "committed_points", "completed_points", "capacity_hours", "risk_score",
                  "external_id", "velocity", "task_count", "created_at"]

    def get_task_count(self, obj):
        return obj.tasks.count()


class TaskSerializer(serializers.ModelSerializer):
    assignee_detail = UserListSerializer(source="assignee", read_only=True)
    work_package_name = serializers.CharField(source="work_package.name", read_only=True)
    sprint_name = serializers.CharField(source="sprint.name", read_only=True)
    cost = serializers.FloatField(read_only=True)
    effort_variance = serializers.FloatField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id", "project", "work_package", "work_package_name", "sprint", "sprint_name",
            "title", "description", "task_type", "priority", "status",
            "assignee", "assignee_detail", "reviewer",
            "estimate_hours", "spent_hours", "story_points",
            "required_skills", "acceptance_criteria",
            "risk_score", "risk_factors", "risk_explanation",
            "blocked", "blocked_reason", "due_date", "completed_at",
            "external_id", "external_url", "created_by_agent", "labels",
            "cost", "effort_variance", "is_overdue", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "completed_at"]


class TaskWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id", "project", "work_package", "sprint", "title", "description", "task_type",
            "priority", "status", "assignee", "reviewer", "estimate_hours", "spent_hours",
            "story_points", "required_skills", "acceptance_criteria", "blocked",
            "blocked_reason", "due_date", "labels", "created_by_agent",
        ]


class RiskAlertSerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source="task.title", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = RiskAlert
        fields = ["id", "project", "project_name", "task", "task_title", "sprint", "category",
                  "severity", "score", "title", "message", "factors", "recommendation",
                  "acknowledged", "acknowledged_by", "acknowledged_at", "detected_at"]
        read_only_fields = ["id", "detected_at"]


class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.full_name", read_only=True)
    author_initials = serializers.CharField(source="author.initials", read_only=True)
    author_color = serializers.CharField(source="author.avatar_color", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "project", "task", "author", "author_name", "author_initials",
                  "author_color", "body", "sentiment", "weak_signal", "created_at"]
        read_only_fields = ["id", "author", "created_at", "sentiment", "weak_signal"]


class IntegrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Integration
        fields = ["id", "owner", "project", "provider", "name", "base_url", "board_key",
                  "workspace", "status", "last_error", "last_sync_at", "auto_sync",
                  "sync_interval_minutes", "created_at"]
        read_only_fields = ["id", "owner", "status", "last_error", "last_sync_at", "created_at"]


class ProjectListSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source="owner.full_name", read_only=True)
    owner_initials = serializers.CharField(source="owner.initials", read_only=True)
    owner_color = serializers.CharField(source="owner.avatar_color", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    task_count = serializers.SerializerMethodField()
    done_count = serializers.SerializerMethodField()
    open_risks = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    is_late = serializers.BooleanField(read_only=True)
    budget_consumed = serializers.FloatField(read_only=True)

    class Meta:
        model = Project
        fields = [
            "id", "reference", "name", "slug", "summary", "status", "health", "methodology",
            "owner", "owner_name", "owner_initials", "owner_color", "team", "team_name",
            "start_date", "target_end_date", "budget", "currency",
            "estimated_effort_hours", "spent_effort_hours", "progress", "risk_score",
            "external_provider", "external_key", "external_url", "tags",
            "task_count", "done_count", "open_risks", "member_count", "is_late",
            "budget_consumed", "created_at", "updated_at",
        ]

    def get_task_count(self, obj):
        return obj.tasks.count()

    def get_done_count(self, obj):
        return obj.tasks.filter(status="DONE").count()

    def get_open_risks(self, obj):
        return obj.risk_alerts.filter(acknowledged=False).count()

    def get_member_count(self, obj):
        return obj.members.count()


class ProjectDetailSerializer(ProjectListSerializer):
    brief = serializers.CharField()
    work_packages = WorkPackageSerializer(many=True, read_only=True)
    sprints = SprintSerializer(many=True, read_only=True)
    recent_tasks = serializers.SerializerMethodField()
    risk_alerts = serializers.SerializerMethodField()
    members_detail = UserListSerializer(source="members", many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    integrations = IntegrationSerializer(many=True, read_only=True)
    latest_runs = serializers.SerializerMethodField()
    health_indicators = serializers.SerializerMethodField()

    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + [
            "brief", "work_packages", "sprints", "recent_tasks", "risk_alerts",
            "members_detail", "comments", "integrations", "latest_runs", "health_indicators",
            "synced_at",
        ]

    def get_recent_tasks(self, obj):
        return TaskSerializer(obj.tasks.select_related("assignee", "sprint", "work_package")[:12], many=True).data

    def get_risk_alerts(self, obj):
        return RiskAlertSerializer(obj.risk_alerts.select_related("task")[:10], many=True).data

    def get_comments(self, obj):
        return CommentSerializer(obj.comments.select_related("author")[:8], many=True).data

    def get_latest_runs(self, obj):
        return AgentRunSerializer(obj.agent_runs.select_related("agent")[:6], many=True).data

    def get_health_indicators(self, obj):
        return {
            "overdue_tasks": obj.overdue_tasks,
            "blocked_tasks": obj.blocked_tasks,
            "effort_variance_pct": _variance(obj),
            "budget_consumed_pct": obj.budget_consumed,
            "progress_pct": obj.progress,
            "risk_score": float(obj.risk_score),
        }


def _variance(project):
    est = float(project.estimated_effort_hours or 0)
    spent = float(project.spent_effort_hours or 0)
    if est <= 0:
        return 0
    return round((spent - est) / est * 100, 1)


class ProjectWriteSerializer(serializers.ModelSerializer):
    member_ids = serializers.PrimaryKeyRelatedField(
        source="members", queryset=User.objects.all(), many=True, required=False
    )

    class Meta:
        model = Project
        fields = ["id", "name", "summary", "brief", "status", "health", "methodology",
                  "team", "member_ids", "start_date", "target_end_date", "budget", "currency",
                  "estimated_effort_hours", "progress", "tags", "external_provider",
                  "external_key", "external_url"]
        read_only_fields = ["id"]
