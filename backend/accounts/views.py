import random
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from rest_framework import generics, permissions, status, views
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from rest_framework_simplejwt.tokens import RefreshToken

from audit.models import AuditLog
from notifications.models import Notification

from .models import PasswordResetCode, Skill, Team, User, UserSkill
from .serializers import (
    AdminUserWriteSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    SkillSerializer,
    TeamSerializer,
    UserListSerializer,
    UserSerializer,
)


def _tokens_for(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def _log(request, action, description, entity_type="", entity_id="", severity="INFO", **extra):
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        action=action,
        description=description,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id else "",
        severity=severity,
        ip_address=_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        metadata=extra.pop("metadata", {}),
    )


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user.touch()
        Notification.objects.create(
            user=user,
            category=Notification.Category.ACCOUNT,
            level=Notification.Level.SUCCESS,
            title="Bienvenue sur Cadria 👋",
            message="Votre espace est prêt. Créez votre premier projet et laissez le copilote proposer un découpage.",
            link="/app/projects/new",
        )
        AuditLog.objects.create(
            actor=user, action=AuditLog.Action.SIGNUP, severity=AuditLog.Severity.NOTICE,
            entity_type="User", entity_id=str(user.pk), entity_label=user.email,
            description="Création de compte", ip_address=_client_ip(request),
        )
        return Response(
            {"user": UserSerializer(user, context={"request": request}).data, **_tokens_for(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        password = request.data.get("password") or ""
        user = authenticate(request, username=email, password=password)
        if user is None:
            return Response({"detail": "Identifiants invalides."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active or user.status == User.Status.SUSPENDED:
            return Response(
                {"detail": "Votre compte est suspendu. Contactez un administrateur."},
                status=status.HTTP_403_FORBIDDEN,
            )
        user.touch()
        AuditLog.objects.create(
            actor=user, action=AuditLog.Action.LOGIN, entity_type="User", entity_id=str(user.pk),
            description="Connexion", ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:255],
        )
        return Response({"user": UserSerializer(user).data, **_tokens_for(user)})


class LogoutView(views.APIView):
    def post(self, request):
        try:
            token = RefreshToken(request.data.get("refresh"))
            token.blacklist()
        except Exception:  # token déjà blacklisté / absent — on ne bloque pas
            pass
        if request.user.is_authenticated:
            AuditLog.objects.create(
                actor=request.user, action=AuditLog.Action.LOGOUT, entity_type="User",
                entity_id=str(request.user.pk), description="Déconnexion", ip_address=_client_ip(request),
            )
        return Response({"detail": "Déconnecté."}, status=status.HTTP_205_RESET_CONTENT)


class MeView(views.APIView):
    def get(self, request):
        request.user.touch()
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(views.APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        AuditLog.objects.create(
            actor=user, action=AuditLog.Action.UPDATE, entity_type="User", entity_id=str(user.pk),
            description="Changement de mot de passe", severity=AuditLog.Severity.NOTICE,
        )
        return Response({"detail": "Mot de passe mis à jour."})


class PasswordResetRequestView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        resp = {"detail": "Si ce compte existe, un code de réinitialisation a été envoyé."}
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return Response(resp)
        code = f"{random.randint(100000, 999999)}"
        PasswordResetCode.objects.create(user=user, code=code, expires_at=timezone.now() + timedelta(minutes=15))
        # Démo : le code est renvoyé dans la réponse (aucun serveur SMTP configuré).
        return Response({**resp, "demo_code": code})


class PasswordResetConfirmView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        code_obj = serializer.validated_data["code_obj"]
        user.set_password(serializer.validated_data["new_password"])
        user.save()
        code_obj.used_at = timezone.now()
        code_obj.save(update_fields=["used_at"])
        return Response({"detail": "Mot de passe réinitialisé. Vous pouvez vous connecter."})


# ---------------------------------------------------------------------------
# Espace utilisateur
# ---------------------------------------------------------------------------
class TeamViewSet(ModelViewSet):
    serializer_class = TeamSerializer
    filterset_fields = []
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        # Annuaire des équipes : visible par tout utilisateur authentifié.
        return Team.objects.prefetch_related("members").all()

    def perform_create(self, serializer):
        team = serializer.save(owner=self.request.user)
        members = serializer.validated_data.get("members", [])
        team.members.add(self.request.user, *members)
        _log(self.request, AuditLog.Action.CREATE, f"Équipe « {team.name} » créée",
             "Team", team.pk, severity=AuditLog.Severity.NOTICE)

    def perform_update(self, serializer):
        team = serializer.save()
        _log(self.request, AuditLog.Action.UPDATE, f"Équipe « {team.name} » modifiée", "Team", team.pk)

    def perform_destroy(self, instance):
        _log(self.request, AuditLog.Action.DELETE, f"Équipe « {instance.name} » supprimée",
             "Team", instance.pk, severity=AuditLog.Severity.WARNING)
        instance.delete()


def models_q_owner_or_member(user):
    from django.db.models import Q
    return Q(owner=user) | Q(members=user)


class SkillViewSet(ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    search_fields = ["name"]
    ordering_fields = ["name", "category"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [permissions.IsAdminUser()]
        return [permissions.IsAuthenticated()]


class MemberDirectoryView(generics.ListAPIView):
    """Annuaire des membres — utilisé par l'équipe et le matching de l'Agent 2."""

    serializer_class = UserListSerializer
    search_fields = ["first_name", "last_name", "email", "job_title", "company"]
    ordering_fields = ["last_name", "role", "created_at"]

    def get_queryset(self):
        return User.objects.filter(is_active=True).select_related().prefetch_related("teams").order_by("last_name")


class MySkillsView(views.APIView):
    def get(self, request):
        return Response(
            [{"skill": us.skill_id, "name": us.skill.name, "category": us.skill.category, "level": us.level}
             for us in request.user.skills.select_related("skill").all()]
        )

    def put(self, request):
        """Remplace la liste de compétences : [{"skill": 3, "level": 4}, ...]"""
        UserSkill.objects.filter(user=request.user).delete()
        for item in request.data if isinstance(request.data, list) else []:
            skill_id = item.get("skill") or item.get("id")
            if not skill_id:
                continue
            UserSkill.objects.update_or_create(
                user=request.user,
                skill_id=skill_id,
                defaults={"level": item.get("level", 3)},
            )
        return Response({"detail": "Compétences mises à jour."})


# ---------------------------------------------------------------------------
# Administration
# ---------------------------------------------------------------------------
class IsAdminRole(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.role == User.Role.ADMIN))


class AdminUserViewSet(ModelViewSet):
    """CRUD complet sur les comptes — réservé à l'espace administration."""

    permission_classes = [IsAdminRole]
    serializer_class = AdminUserWriteSerializer
    search_fields = ["first_name", "last_name", "email", "company", "job_title"]
    ordering_fields = ["created_at", "last_name", "role", "status", "last_seen_at"]

    def get_queryset(self):
        qs = User.objects.prefetch_related("teams").all()
        role = self.request.query_params.get("role")
        status_ = self.request.query_params.get("status")
        if role:
            qs = qs.filter(role=role)
        if status_:
            qs = qs.filter(status=status_)
        if self.request.query_params.get("active") == "true":
            qs = qs.filter(is_active=True)
        return qs

    def retrieve(self, request, *args, **kwargs):
        return Response(UserSerializer(self.get_object()).data)

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(UserListSerializer(page, many=True).data)
        return Response(UserListSerializer(qs, many=True).data)

    def perform_create(self, serializer):
        user = serializer.save()
        _log(self.request, AuditLog.Action.CREATE, f"Compte créé pour {user.email}",
             "User", user.pk, severity=AuditLog.Severity.NOTICE)

    def perform_update(self, serializer):
        before = {f: getattr(serializer.instance, f, None) for f in ("role", "status", "is_active")}
        user = serializer.save()
        after = {f: getattr(user, f) for f in before}
        _log(self.request, AuditLog.Action.UPDATE, f"Compte {user.email} modifié", "User", user.pk,
             metadata={"before": before, "after": after})

    def perform_destroy(self, instance):
        email = instance.email
        _log(self.request, AuditLog.Action.DELETE, f"Compte {email} supprimé", "User", instance.pk,
             severity=AuditLog.Severity.CRITICAL)
        instance.delete()

    @action(detail=True, methods=["post"])
    def toggle_active(self, request, pk=None):
        user = self.get_object()
        user.is_active = not user.is_active
        user.status = User.Status.ACTIVE if user.is_active else User.Status.SUSPENDED
        user.save(update_fields=["is_active", "status"])
        _log(request, AuditLog.Action.PERMISSION,
             f"Compte {user.email} {'activé' if user.is_active else 'suspendu'}",
             "User", user.pk, severity=AuditLog.Severity.WARNING)
        return Response({"is_active": user.is_active, "status": user.status})

    @action(detail=True, methods=["post"])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_pwd = request.data.get("password") or "Cadria@2026"
        user.set_password(new_pwd)
        user.save()
        _log(request, AuditLog.Action.PERMISSION, f"Mot de passe réinitialisé pour {user.email}",
             "User", user.pk, severity=AuditLog.Severity.WARNING)
        return Response({"detail": "Mot de passe réinitialisé.", "password": new_pwd})

    @action(detail=False, methods=["post"])
    def bulk_action(self, request):
        ids = request.data.get("ids", [])
        act = request.data.get("action")
        qs = User.objects.filter(pk__in=ids)
        count = 0
        if act == "activate":
            count = qs.update(is_active=True, status=User.Status.ACTIVE)
        elif act == "suspend":
            count = qs.update(is_active=False, status=User.Status.SUSPENDED)
        elif act == "delete":
            count = qs.count()
            qs.delete()
        elif act == "role":
            count = qs.update(role=request.data.get("role", User.Role.MEMBER))
        _log(request, AuditLog.Action.UPDATE, f"Action groupée « {act} » sur {count} compte(s)",
             "User", severity=AuditLog.Severity.WARNING, metadata={"ids": ids, "action": act})
        return Response({"updated": count})
