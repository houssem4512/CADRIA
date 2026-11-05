from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.models import User
from audit.models import AuditLog

from .models import Notification, NotificationPreference, NotificationRead
from .serializers import (
    BroadcastSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)


def _visible(user):
    """Notifications personnelles + diffusions globales visibles par l'utilisateur."""
    role_filter = Q(target_role="ALL") | Q(target_role=user.role)
    return Notification.objects.filter(Q(user=user) | (Q(is_broadcast=True) & role_filter))


class NotificationViewSet(ModelViewSet):
    serializer_class = NotificationSerializer
    filterset_backends = []
    search_fields = ["title", "message"]

    def get_queryset(self):
        qs = _visible(self.request.user).select_related("user")
        category = self.request.query_params.get("category")
        level = self.request.query_params.get("level")
        unread = self.request.query_params.get("unread")
        archived = self.request.query_params.get("archived")
        if category:
            qs = qs.filter(category=category)
        if level:
            qs = qs.filter(level=level)
        if unread == "true":
            qs = qs.filter(read=False)
        if archived == "true":
            qs = qs.filter(archived=True)
        else:
            qs = qs.filter(archived=False)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["current_user"] = self.request.user
        return ctx

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = _visible(request.user).filter(archived=False)
        data = {
            "unread": qs.filter(read=False).count(),
            "total": qs.count(),
            "by_level": {
                lv: qs.filter(level=lv).count() for lv, _ in Notification.Level.choices
            },
            "by_category": {
                c: qs.filter(category=c).count() for c, _ in Notification.Category.choices
            },
        }
        return Response(data)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        qs = _visible(request.user).filter(read=False)
        ids = list(qs.values_list("pk", flat=True))
        Notification.objects.filter(pk__in=ids, user=request.user).update(
            read=True, read_at=timezone.now()
        )
        for n in Notification.objects.filter(pk__in=ids, is_broadcast=True):
            NotificationRead.objects.get_or_create(notification=n, user=request.user)
        return Response({"marked": len(ids)})

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        n = self.get_object()
        if n.user_id == request.user.pk:
            n.read = True
            n.read_at = timezone.now()
            n.save(update_fields=["read", "read_at"])
        else:
            NotificationRead.objects.get_or_create(notification=n, user=request.user)
        return Response({"read": True})

    @action(detail=True, methods=["post"])
    def mark_unread(self, request, pk=None):
        n = self.get_object()
        if n.user_id == request.user.pk:
            n.read = False
            n.read_at = None
            n.save(update_fields=["read", "read_at"])
        else:
            NotificationRead.objects.filter(notification=n, user=request.user).delete()
        return Response({"read": False})

    @action(detail=True, methods=["post"])
    def toggle_star(self, request, pk=None):
        n = self.get_object()
        if n.user_id != request.user.pk:
            return Response({"detail": "Action non autorisée sur une diffusion."}, status=403)
        n.starred = not n.starred
        n.save(update_fields=["starred"])
        return Response({"starred": n.starred})

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        n = self.get_object()
        if n.user_id != request.user.pk:
            return Response({"detail": "Action non autorisée sur une diffusion."}, status=403)
        n.archived = not n.archived
        n.save(update_fields=["archived"])
        return Response({"archived": n.archived})

    @action(detail=True, methods=["delete"], url_path="delete")
    def destroy_one(self, request, pk=None):
        n = self.get_object()
        if n.user_id != request.user.pk:
            return Response({"detail": "Action non autorisée sur une diffusion."}, status=403)
        n.delete()
        return Response(status=204)

    def destroy(self, request, *args, **kwargs):
        return self.destroy_one(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        """Création d'une notification personnelle (usage interne / tests)."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, is_broadcast=False)
        return Response(serializer.data, status=201)


class BroadcastView(views.APIView):
    """Diffusion d'une annonce par l'administration."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not (request.user.is_superuser or request.user.role == User.Role.ADMIN):
            return Response({"detail": "Réservé aux administrateurs."}, status=403)
        serializer = BroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        recipients = [request.user.pk]
        target_role = data.get("target_role") or "ALL"
        if data.get("targets"):
            recipients = list(User.objects.filter(pk__in=data["targets"]).values_list("pk", flat=True))
            target_role = "ALL"
        notif = Notification.objects.create(
            user=None,
            is_broadcast=True,
            target_role=target_role,
            category=data.get("category", Notification.Category.SYSTEM),
            level=data.get("level", Notification.Level.INFO),
            title=data["title"],
            message=data.get("message", ""),
            link=data.get("link", ""),
            metadata={"sent_by": request.user.pk, "recipients": len(recipients)},
        )
        AuditLog.objects.create(
            actor=request.user, action=AuditLog.Action.CREATE, entity_type="Notification",
            entity_id=str(notif.pk), entity_label=notif.title,
            description=f"Diffusion d'une annonce ({target_role})", severity=AuditLog.Severity.NOTICE,
        )
        return Response({"id": notif.pk, "broadcast": True, "target_role": target_role}, status=201)


class NotificationPreferenceView(views.APIView):
    def get(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return Response(NotificationPreferenceSerializer(pref).data)

    def patch(self, request):
        pref, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
