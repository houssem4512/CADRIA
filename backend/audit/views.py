from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework import filters as rf_filters
from rest_framework import viewsets, views
from rest_framework.response import Response

from accounts.models import User

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AuditLogSerializer
    filter_backends = [rf_filters.SearchFilter, rf_filters.OrderingFilter]
    search_fields = ["description", "entity_label", "actor_label", "entity_type", "agent_key"]
    ordering_fields = ["created_at", "action", "severity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = AuditLog.objects.select_related("actor", "run").all()
        params = self.request.query_params
        user = self.request.user
        is_admin = user.is_superuser or user.role == User.Role.ADMIN

        # Un non-admin ne voit que ses propres actions + celles de ses projets
        if not is_admin and params.get("scope") != "all":
            qs = qs.filter(Q(actor=user))

        if params.get("action"):
            qs = qs.filter(action=params["action"])
        if params.get("severity"):
            qs = qs.filter(severity=params["severity"])
        if params.get("entity_type"):
            qs = qs.filter(entity_type=params["entity_type"])
        if params.get("entity_id"):
            qs = qs.filter(entity_id=params["entity_id"])
        if params.get("agent"):
            qs = qs.filter(agent_key=params["agent"])
        if params.get("actor"):
            qs = qs.filter(actor_id=params["actor"])
        days = params.get("days")
        if days:
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=int(days)))
        return qs


class AuditSummaryView(views.APIView):
    def get(self, request):
        is_admin = request.user.is_superuser or request.user.role == User.Role.ADMIN
        qs = AuditLog.objects.all()
        if not is_admin:
            qs = qs.filter(actor=request.user)
        since = timezone.now() - timedelta(days=30)
        recent = qs.filter(created_at__gte=since)
        return Response({
            "total": qs.count(),
            "last_30_days": recent.count(),
            "by_action": [
                {"key": a.value, "label": a.label, "count": qs.filter(action=a.value).count()}
                for a in AuditLog.Action
            ],
            "by_severity": [
                {"key": s.value, "label": s.label, "count": qs.filter(severity=s.value).count()}
                for s in AuditLog.Severity
            ],
            "by_agent": [
                {"key": k, "count": c}
                for k, c in qs.exclude(agent_key="").values_list("agent_key")
                .annotate(c=Count("id")).order_by("-c")
            ],
            "timeline": [
                {"date": r["d"].isoformat(), "count": r["c"]}
                for r in recent.annotate(d=TruncDate("created_at")).values("d")
                .annotate(c=Count("id")).order_by("d")
            ],
        })
