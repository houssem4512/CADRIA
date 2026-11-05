"""Statistiques & pilotage — alimente le dashboard client et le dashboard admin."""
from collections import defaultdict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone
from rest_framework import views
from rest_framework.response import Response

from accounts.models import Team, User
from audit.models import AuditLog
from notifications.models import Notification
from orchestration.models import AgentRun, AssignmentSuggestion, Proposal
from projects.models import Comment, Project, RiskAlert, Sprint, Task

User = get_user_model()


def _pct(n, d):
    return round(n / d * 100, 1) if d else 0


class ClientDashboardView(views.APIView):
    """Tableau de bord de l'espace client / chef de projet."""

    def get(self, request):
        user = request.user
        projects = Project.objects.filter(Q(owner=user) | Q(members=user)).distinct()
        project_ids = list(projects.values_list("pk", flat=True))
        tasks = Task.objects.filter(project_id__in=project_ids)
        open_tasks = tasks.exclude(status="DONE")

        kpis = {
            "projects": projects.count(),
            "active_projects": projects.filter(status="ACTIVE").count(),
            "at_risk": projects.filter(health="RED").count(),
            "tasks_total": tasks.count(),
            "tasks_done": tasks.filter(status="DONE").count(),
            "tasks_open": open_tasks.count(),
            "tasks_overdue": sum(1 for t in open_tasks if t.is_overdue),
            "tasks_blocked": open_tasks.filter(blocked=True).count(),
            "completion_rate": _pct(tasks.filter(status="DONE").count(), tasks.count()),
            "open_alerts": RiskAlert.objects.filter(project_id__in=project_ids, acknowledged=False).count(),
            "critical_alerts": RiskAlert.objects.filter(
                project_id__in=project_ids, acknowledged=False, severity="CRITICAL").count(),
            "pending_validations": Proposal.objects.filter(
                project_id__in=project_ids, status="PENDING").count(),
            "unread_notifications": Notification.objects.filter(user=user, read=False, archived=False).count(),
            "team_members": User.objects.filter(teams__projects__in=project_ids).distinct().count()
            if project_ids else 0,
            "estimated_hours": float(tasks.aggregate(s=Sum("estimate_hours"))["s"] or 0),
            "spent_hours": float(tasks.aggregate(s=Sum("spent_hours"))["s"] or 0),
        }
        kpis["effort_variance_pct"] = (
            round((kpis["spent_hours"] - kpis["estimated_hours"]) / kpis["estimated_hours"] * 100, 1)
            if kpis["estimated_hours"] else 0
        )

        # Répartition par statut
        status_dist = [
            {"key": s.value, "label": s.label, "count": tasks.filter(status=s.value).count()}
            for s in Task.Status
        ]
        # Répartition par priorité
        prio_dist = [
            {"key": p.value, "label": p.label, "count": open_tasks.filter(priority=p.value).count()}
            for p in Task.Priority
        ]
        # Santé du portefeuille
        health_dist = [
            {"key": h.value, "label": h.label, "count": projects.filter(health=h.value).count()}
            for h in Project.Health
        ]
        # Vélocité par sprint (6 derniers)
        sprints = (Sprint.objects.filter(project_id__in=project_ids, status="COMPLETED")
                   .order_by("-end_date")[:6])
        velocity = [
            {"name": s.name, "planned": float(s.committed_points), "delivered": float(s.completed_points)}
            for s in reversed(list(sprints))
        ]
        # Burn-up / avancement sur 12 semaines
        today = timezone.now().date()
        weeks = []
        for i in range(11, -1, -1):
            end = today - timedelta(weeks=i)
            start = end - timedelta(days=6)
            done = tasks.filter(status="DONE", completed_at__date__range=(start, end)).count()
            created = tasks.filter(created_at__date__range=(start, end)).count()
            weeks.append({"week": start.isoformat(), "done": done, "created": created})
        cum = 0
        for w in weeks:
            cum += w["done"]
            w["cumulative_done"] = cum

        # Risques par catégorie
        risk_by_cat = [
            {"key": c.value, "label": c.label,
             "count": RiskAlert.objects.filter(project_id__in=project_ids, category=c.value,
                                               acknowledged=False).count()}
            for c in RiskAlert.Category
        ]

        # Charge de l'équipe (top 6)
        workload = []
        seen = set()
        for p in projects.prefetch_related("members"):
            for m in p.members.all():
                if m.pk in seen:
                    continue
                seen.add(m.pk)
                est = open_tasks.filter(assignee=m).aggregate(s=Sum("estimate_hours"))["s"] or 0
                capacity = float(m.weekly_capacity_hours or 0)
                workload.append({
                    "id": m.pk, "name": m.full_name, "initials": m.initials, "color": m.avatar_color,
                    "job_title": m.job_title, "estimated": float(est), "capacity": capacity,
                    "utilisation": round(float(est) / capacity * 100, 1) if capacity else 0,
                })
        workload.sort(key=lambda r: -r["utilisation"])
        workload = workload[:6]

        # Activité récente
        activity = [
            {
                "id": a.pk, "action": a.action, "label": a.get_action_display(),
                "description": a.description, "entity": a.entity_label,
                "entity_type": a.entity_type, "severity": a.severity,
                "agent": a.agent_key, "created_at": a.created_at.isoformat(),
            }
            for a in AuditLog.objects.filter(
                Q(actor=user) | Q(entity_type="Project", entity_id__in=[str(i) for i in project_ids[:50]])
            ).select_related("actor").order_by("-created_at")[:12]
        ]

        # Notifications récentes
        recent_notifications = [
            {"id": n.pk, "title": n.title, "message": n.message, "level": n.level,
             "category": n.category, "read": n.read, "link": n.link,
             "created_at": n.created_at.isoformat()}
            for n in Notification.objects.filter(user=user, archived=False).order_by("-created_at")[:6]
        ]

        upcoming = [
            {"id": t.pk, "title": t.title, "project": t.project.name,
             "project_id": t.project_id, "due_date": t.due_date.isoformat() if t.due_date else None,
             "priority": t.priority, "status": t.status}
            for t in open_tasks.filter(due_date__isnull=False).order_by("due_date")[:6]
        ]

        return Response({
            "kpis": kpis,
            "status_distribution": status_dist,
            "priority_distribution": prio_dist,
            "health_distribution": health_dist,
            "velocity": velocity,
            "progress_timeline": weeks,
            "risk_by_category": risk_by_cat,
            "workload": workload,
            "activity": activity,
            "recent_notifications": recent_notifications,
            "upcoming_deadlines": upcoming,
        })


class AdminDashboardView(views.APIView):
    """Tableau de bord de l'espace administration."""

    def get(self, request):
        if not (request.user.is_superuser or request.user.role == User.Role.ADMIN):
            return Response({"detail": "Réservé aux administrateurs."}, status=403)

        users = User.objects.all()
        projects = Project.objects.all()
        tasks = Task.objects.all()
        thirty_days_ago = timezone.now() - timedelta(days=30)

        kpis = {
            "users": users.count(),
            "users_active": users.filter(is_active=True, status="ACTIVE").count(),
            "users_pending": users.filter(status="PENDING").count(),
            "users_suspended": users.filter(status="SUSPENDED").count(),
            "new_users_30d": users.filter(created_at__gte=thirty_days_ago).count(),
            "admins": users.filter(Q(role="ADMIN") | Q(is_superuser=True)).count(),
            "projects": projects.count(),
            "projects_active": projects.filter(status="ACTIVE").count(),
            "projects_at_risk": projects.filter(health="RED").count(),
            "tasks": tasks.count(),
            "tasks_done": tasks.filter(status="DONE").count(),
            "completion_rate": _pct(tasks.filter(status="DONE").count(), tasks.count()),
            "teams": Team.objects.count(),
            "open_alerts": RiskAlert.objects.filter(acknowledged=False).count(),
            "agent_runs": AgentRun.objects.count(),
            "agent_runs_30d": AgentRun.objects.filter(created_at__gte=thirty_days_ago).count(),
            "pending_validations": Proposal.objects.filter(status="PENDING").count(),
            "unread_notifications": Notification.objects.filter(read=False, archived=False).count(),
            "estimated_hours": float(tasks.aggregate(s=Sum("estimate_hours"))["s"] or 0),
            "spent_hours": float(tasks.aggregate(s=Sum("spent_hours"))["s"] or 0),
            "budget_total": float(projects.aggregate(s=Sum("budget"))["s"] or 0),
        }
        kpis["platform_health"] = _platform_health(kpis)

        # Évolution des inscriptions et des projets (6 derniers mois)
        growth = []
        for i in range(5, -1, -1):
            end = timezone.now() - timedelta(days=30 * i)
            start = end - timedelta(days=30)
            growth.append({
                "month": end.strftime("%b %Y"),
                "users": users.filter(created_at__gte=start, created_at__lt=end).count(),
                "projects": projects.filter(created_at__gte=start, created_at__lt=end).count(),
            })

        role_dist = [
            {"key": r.value, "label": r.label, "count": users.filter(role=r.value).count()}
            for r in User.Role
        ]
        status_dist = [
            {"key": s.value, "label": s.label, "count": users.filter(status=s.value).count()}
            for s in User.Status
        ]
        project_status = [
            {"key": s.value, "label": s.label, "count": projects.filter(status=s.value).count()}
            for s in Project.Status
        ]

        # Exécutions d'agents par statut
        agent_activity = [
            {"day": r["d"].isoformat(), "runs": r["c"],
             "failed": r["f"]}
            for r in AgentRun.objects.filter(created_at__gte=thirty_days_ago)
            .annotate(d=TruncDate("created_at")).values("d")
            .annotate(c=Count("id"), f=Count("id", filter=Q(status="FAILED"))).order_by("d")
        ]

        top_projects = [
            {"id": p.pk, "reference": p.reference, "name": p.name, "progress": p.progress,
             "risk_score": float(p.risk_score), "health": p.health,
             "owner": p.owner.full_name, "tasks": p.tasks.count()}
            for p in projects.select_related("owner").order_by("-risk_score")[:6]
        ]

        recent_users = [
            {"id": u.pk, "name": u.full_name, "email": u.email, "role": u.role,
             "status": u.status, "initials": u.initials, "color": u.avatar_color,
             "created_at": u.created_at.isoformat()}
            for u in users.order_by("-created_at")[:6]
        ]

        activity = [
            {"id": a.pk, "action": a.action, "label": a.get_action_display(),
             "description": a.description, "actor": a.actor_display, "entity": a.entity_label,
             "entity_type": a.entity_type, "severity": a.severity, "agent": a.agent_key,
             "created_at": a.created_at.isoformat()}
            for a in AuditLog.objects.select_related("actor").order_by("-created_at")[:20]
        ]

        # Activité plateforme (30 jours)
        daily = defaultdict(lambda: {"actions": 0, "logins": 0})
        for r in (AuditLog.objects.filter(created_at__gte=thirty_days_ago)
                  .annotate(d=TruncDate("created_at")).values("d")
                  .annotate(c=Count("id")).order_by("d")):
            daily[r["d"].isoformat()]["actions"] = r["c"]
        for r in (AuditLog.objects.filter(created_at__gte=thirty_days_ago, action="LOGIN")
                  .annotate(d=TruncDate("created_at")).values("d")
                  .annotate(c=Count("id")).order_by("d")):
            daily[r["d"].isoformat()]["logins"] = r["c"]
        activity_timeline = [{"date": k, **v} for k, v in sorted(daily.items())]

        return Response({
            "kpis": kpis,
            "growth": growth,
            "role_distribution": role_dist,
            "user_status_distribution": status_dist,
            "project_status_distribution": project_status,
            "agent_activity": agent_activity,
            "top_risky_projects": top_projects,
            "recent_users": recent_users,
            "activity": activity,
            "activity_timeline": activity_timeline,
        })


def _platform_health(k):
    score = 100
    score -= min(30, k["projects_at_risk"] * 6)
    score -= min(20, k["open_alerts"] * 2)
    score -= min(15, k["pending_validations"] * 3)
    if k["completion_rate"] < 50:
        score -= 10
    return max(0, min(100, score))


class PlatformInsightsView(views.APIView):
    """Statistiques transverses : qualité de génération, équilibrage, risques."""

    def get(self, request):
        if not (request.user.is_superuser or request.user.role == User.Role.ADMIN):
            return Response({"detail": "Réservé aux administrateurs."}, status=403)

        tasks = Task.objects.all()
        agent_tasks = tasks.filter(created_by_agent=True)
        manual_tasks = tasks.exclude(created_by_agent=True)

        est_gap_agent = _avg_gap(agent_tasks)
        est_gap_manual = _avg_gap(manual_tasks)

        # Équilibrage de charge (indice de Gini simplifié sur les utilisations)
        utils = []
        for u in User.objects.filter(is_active=True):
            est = u.assigned_tasks.exclude(status="DONE").aggregate(s=Sum("estimate_hours"))["s"] or 0
            cap = float(u.weekly_capacity_hours or 0)
            if cap:
                utils.append(min(2.0, float(est) / cap))
        balance = round(100 - (_gini(utils) * 100), 1) if len(utils) > 1 else 100

        return Response({
            "generation_quality": {
                "agent_tasks": agent_tasks.count(),
                "manual_tasks": manual_tasks.count(),
                "avg_estimate_gap_agent_pct": est_gap_agent,
                "avg_estimate_gap_manual_pct": est_gap_manual,
                "acceptance_rate": _pct(
                    Proposal.objects.filter(status__in=["APPROVED", "APPLIED"]).count(),
                    Proposal.objects.exclude(status="PENDING").count(),
                ),
            },
            "assignment_quality": {
                "load_balance_index": balance,
                "avg_utilisation_pct": round(sum(utils) / len(utils) * 100, 1) if utils else 0,
                "overloaded_members": sum(1 for u in utils if u > 1),
                "suggestions_accepted": _pct(
                    AssignmentSuggestion.objects.filter(accepted=True).count(),
                    AssignmentSuggestion.objects.exclude(accepted=None).count(),
                ),
            },
            "risk_quality": {
                "alerts_total": RiskAlert.objects.count(),
                "alerts_open": RiskAlert.objects.filter(acknowledged=False).count(),
                "avg_project_risk": round(float(
                    Project.objects.aggregate(a=Avg("risk_score"))["a"] or 0), 1),
                "projects_late": sum(1 for p in Project.objects.all() if p.is_late),
            },
            "comments": {
                "total": Comment.objects.count(),
                "weak_signals": Comment.objects.filter(weak_signal=True).count(),
            },
        })


def _avg_gap(qs):
    vals = []
    for t in qs.exclude(estimate_hours=0):
        if float(t.estimate_hours) > 0:
            vals.append(abs(float(t.spent_hours) - float(t.estimate_hours)) / float(t.estimate_hours) * 100)
    return round(sum(vals) / len(vals), 1) if vals else 0


def _gini(xs):
    xs = sorted(xs)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0
    cum = sum((i + 1) * x for i, x in enumerate(xs))
    return (2 * cum) / (n * total) - (n + 1) / n
