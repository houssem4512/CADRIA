"""
MLOps Dashboard — built-in Django dashboard page.

Accessible at: http://localhost:8000/api/mlops/dashboard/
"""
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Avg, Count
from datetime import timedelta
from collections import defaultdict

from orchestration.models import AgentRun, AgentDefinition
from projects.models import Project, Task, RiskAlert


def dashboard_view(request):
    """Render the MLOps dashboard page."""
    now = timezone.now()
    last_30d = now - timedelta(days=30)

    # Agent runs statistics
    agents_data = []
    for agent_def in AgentDefinition.objects.all().order_by("order"):
        runs = AgentRun.objects.filter(agent=agent_def, created_at__gte=last_30d)
        total = runs.count()
        succeeded = runs.filter(status=AgentRun.Status.SUCCEEDED).count()
        failed = runs.filter(status=AgentRun.Status.FAILED).count()
        skipped = runs.filter(status=AgentRun.Status.SKIPPED).count()
        avg_latency = runs.aggregate(a=Avg("latency_ms"))["a"] or 0
        success_rate = round(succeeded / max(total, 1) * 100, 1)

        agents_data.append({
            "key": agent_def.key,
            "name": agent_def.name,
            "color": agent_def.color,
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "avg_latency_ms": round(avg_latency),
            "success_rate": success_rate,
            "total_runs": agent_def.total_runs or 0,
            "last_run_at": agent_def.last_run_at,
        })

    # Project health
    projects = Project.objects.all()
    project_health = {
        "total": projects.count(),
        "green": projects.filter(health="GREEN").count(),
        "amber": projects.filter(health="AMBER").count(),
        "red": projects.filter(health="RED").count(),
        "avg_risk_score": round(
            projects.exclude(risk_score=0).aggregate(a=Avg("risk_score"))["a"] or 0, 2
        ),
    }

    # Task statistics
    tasks = Task.objects.all()
    task_stats = {
        "total": tasks.count(),
        "todo": tasks.filter(status="TODO").count(),
        "in_progress": tasks.filter(status="IN_PROGRESS").count(),
        "review": tasks.filter(status="REVIEW").count(),
        "done": tasks.filter(status="DONE").count(),
        "blocked": tasks.filter(blocked=True).count(),
        "pushed_to_trello": tasks.exclude(external_id="").count(),
    }

    # Risk alerts
    alerts = RiskAlert.objects.all()
    risk_stats = {
        "total": alerts.count(),
        "open": alerts.filter(acknowledged=False).count(),
        "critical": alerts.filter(severity="CRITICAL", acknowledged=False).count(),
        "warning": alerts.filter(severity="WARNING", acknowledged=False).count(),
        "acknowledged": alerts.filter(acknowledged=True).count(),
    }

    # Recent runs (last 20)
    recent_runs = []
    for r in AgentRun.objects.filter(created_at__gte=last_30d).order_by("-created_at")[:20]:
        recent_runs.append({
            "id": r.id,
            "agent_key": r.agent.key if r.agent else "?",
            "agent_color": r.agent.color if r.agent else "#64748B",
            "project_name": r.project.name if r.project else "—",
            "status": r.status,
            "step": (r.step or "")[:60],
            "latency_ms": r.latency_ms or 0,
            "trigger": r.trigger,
            "created_at": r.created_at.strftime("%d/%m %H:%M"),
            "error_message": r.error_message,
        })

    # Timeline data (runs per day per agent)
    from django.db.models.functions import TruncDate
    timeline = (
        AgentRun.objects.filter(created_at__gte=last_30d)
        .annotate(day=TruncDate("created_at"))
        .values("day", "agent__key")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    timeline_data = defaultdict(lambda: defaultdict(int))
    for entry in timeline:
        day_str = entry["day"].strftime("%d/%m")
        agent_key = entry["agent__key"] or "UNKNOWN"
        timeline_data[day_str][agent_key] += entry["count"]

    timeline_list = []
    for day, agents in sorted(timeline_data.items()):
        timeline_list.append({
            "day": day,
            "SCOPING": agents.get("SCOPING", 0),
            "OPS": agents.get("OPS", 0),
            "RISK": agents.get("RISK", 0),
        })

    context = {
        "agents": agents_data,
        "project_health": project_health,
        "task_stats": task_stats,
        "risk_stats": risk_stats,
        "recent_runs": recent_runs,
        "timeline": timeline_list,
        "mlflow_url": "http://localhost:5000",
    }

    return render(request, "mlops/dashboard.html", context)