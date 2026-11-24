"""
MLOps metrics endpoint — exposes agent statistics for Grafana.

GET /api/metrics/           → JSON summary of all agent runs
GET /api/metrics/agents/    → Per-agent aggregated stats
GET /api/metrics/timeline/  → Time-series data for Grafana graphs
"""
from __future__ import annotations
from datetime import timedelta
from collections import defaultdict

from django.utils import timezone
from django.db.models import Avg, Count, Q
from rest_framework import views, permissions
from rest_framework.response import Response

from orchestration.models import AgentRun, AgentDefinition
from projects.models import Project, Task, RiskAlert
from audit.models import AuditLog

from .tracking import read_metrics_log


class MetricsOverviewView(views.APIView):
    """Dashboard overview — KPIs for all agents."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        last_30d = now - timedelta(days=30)

        # AgentRun statistics
        runs_qs = AgentRun.objects.filter(created_at__gte=last_30d)
        runs_by_agent = {}
        for agent_key in ["SCOPING", "OPS", "RISK"]:
            agent_runs = runs_qs.filter(agent__key=agent_key)
            runs_by_agent[agent_key] = {
                "total": agent_runs.count(),
                "succeeded": agent_runs.filter(status=AgentRun.Status.SUCCEEDED).count(),
                "failed": agent_runs.filter(status=AgentRun.Status.FAILED).count(),
                "skipped": agent_runs.filter(status=AgentRun.Status.SKIPPED).count(),
                "avg_latency_ms": round(agent_runs.aggregate(a=Avg("latency_ms"))["a"] or 0),
                "success_rate": round(
                    agent_runs.filter(status=AgentRun.Status.SUCCEEDED).count() /
                    max(agent_runs.count(), 1) * 100, 1
                ),
            }

        # Project statistics
        projects = Project.objects.all()
        project_stats = {
            "total": projects.count(),
            "with_tasks": projects.filter(task_count__gt=0).count(),
            "avg_risk_score": round(
                projects.exclude(risk_score=0).aggregate(a=Avg("risk_score"))["a"] or 0, 2
            ),
            "green": projects.filter(health="GREEN").count(),
            "amber": projects.filter(health="AMBER").count(),
            "red": projects.filter(health="RED").count(),
        }

        # Task statistics
        tasks = Task.objects.all()
        task_stats = {
            "total": tasks.count(),
            "done": tasks.filter(status="DONE").count(),
            "in_progress": tasks.filter(status="IN_PROGRESS").count(),
            "todo": tasks.filter(status="TODO").count(),
            "blocked": tasks.filter(blocked=True).count(),
            "pushed_to_trello": tasks.exclude(external_id="").count(),
        }

        # Risk alert statistics
        alerts = RiskAlert.objects.all()
        alert_stats = {
            "total": alerts.count(),
            "open": alerts.filter(acknowledged=False).count(),
            "critical": alerts.filter(severity="CRITICAL", acknowledged=False).count(),
            "warning": alerts.filter(severity="WARNING", acknowledged=False).count(),
            "acknowledged": alerts.filter(acknowledged=True).count(),
        }

        # Audit log statistics
        audit_qs = AuditLog.objects.filter(created_at__gte=last_30d)
        audit_stats = {
            "total_actions": audit_qs.count(),
            "agent_actions": audit_qs.filter(agent_key__isnull=False).exclude(agent_key="").count(),
            "by_agent": dict(
                audit_qs.exclude(agent_key="").values_list("agent_key").annotate(
                    count=Count("id")
                ).values_list("agent_key", "count")
            ),
        }

        return Response({
            "period": "last_30_days",
            "agents": runs_by_agent,
            "projects": project_stats,
            "tasks": task_stats,
            "risk_alerts": alert_stats,
            "audit": audit_stats,
        })


class MetricsAgentDetailView(views.APIView):
    """Per-agent detailed metrics."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, agent_key):
        now = timezone.now()
        last_30d = now - timedelta(days=30)

        try:
            agent = AgentDefinition.objects.get(key=agent_key)
        except AgentDefinition.DoesNotExist:
            return Response({"detail": f"Agent {agent_key} not found"}, status=404)

        runs = AgentRun.objects.filter(agent__key=agent_key, created_at__gte=last_30d).order_by("-created_at")

        runs_data = []
        for r in runs[:20]:  # Last 20 runs
            runs_data.append({
                "id": r.id,
                "project": r.project.name if r.project else None,
                "status": r.status,
                "step": r.step,
                "latency_ms": r.latency_ms,
                "trigger": r.trigger,
                "created_at": r.created_at.isoformat(),
                "tokens_in": (r.output_payload or {}).get("tokens_in", 0) if agent_key == "SCOPING" else None,
                "tokens_out": (r.output_payload or {}).get("tokens_out", 0) if agent_key == "SCOPING" else None,
                "error_message": r.error_message,
            })

        # Aggregated stats
        stats = {
            "agent_key": agent_key,
            "agent_name": agent.name,
            "total_runs_30d": runs.count(),
            "avg_latency_ms": round(runs.aggregate(a=Avg("latency_ms"))["a"] or 0),
            "success_rate": round(
                runs.filter(status=AgentRun.Status.SUCCEEDED).count() /
                max(runs.count(), 1) * 100, 1
            ),
            "recent_runs": runs_data,
        }

        return Response(stats)


class MetricsTimelineView(views.APIView):
    """Time-series data for Grafana graphs — agent runs per day."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get("days", 30))
        since = timezone.now() - timedelta(days=days)

        from django.db.models.functions import TruncDate

        # Runs per day per agent
        timeline = (
            AgentRun.objects.filter(created_at__gte=since)
            .annotate(day=TruncDate("created_at"))
            .values("day", "agent__key", "status")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        # Build time-series structure
        by_day: dict = defaultdict(lambda: defaultdict(dict))
        for entry in timeline:
            day = entry["day"].isoformat()
            agent = entry["agent__key"]
            status = entry["status"]
            by_day[day][agent][status] = entry["count"]

        series = []
        for day, agents in sorted(by_day.items()):
            row = {"date": day}
            for agent_key in ["SCOPING", "OPS", "RISK"]:
                agent_data = agents.get(agent_key, {})
                row[f"{agent_key}_total"] = sum(agent_data.values())
                row[f"{agent_key}_succeeded"] = agent_data.get("SUCCEEDED", 0)
                row[f"{agent_key}_failed"] = agent_data.get("FAILED", 0)
            series.append(row)

        return Response({
            "days": days,
            "series": series,
        })


class MetricsMlflowLogView(views.APIView):
    """Read the MLflow-style JSONL log (fallback when MLflow server is not running)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get("limit", 100))
        records = read_metrics_log(limit=limit)
        return Response({
            "count": len(records),
            "records": records,
        })
