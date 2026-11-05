from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers

from .models import PasswordResetCode, Skill, Team, User, UserSkill


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "category"]


class UserSkillSerializer(serializers.ModelSerializer):
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    skill_category = serializers.CharField(source="skill.category", read_only=True)

    class Meta:
        model = UserSkill
        fields = ["id", "skill", "skill_name", "skill_category", "level"]


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    skills = UserSkillSerializer(many=True, read_only=True)
    team_names = serializers.SerializerMethodField()
    active_tasks = serializers.SerializerMethodField()
    workload_hours = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "initials",
            "role", "status", "phone", "job_title", "avatar_color", "bio",
            "company", "timezone", "locale", "is_active", "is_staff",
            "notify_email", "notify_push", "notify_risk_alerts",
            "notify_assignments", "notify_agent_runs", "notify_weekly_digest",
            "weekly_capacity_hours", "hourly_cost",
            "skills", "team_names", "active_tasks", "workload_hours",
            "last_seen_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_staff", "created_at", "updated_at", "last_seen_at"]

    def get_team_names(self, obj):
        return list(obj.teams.values_list("name", flat=True))

    def get_active_tasks(self, obj):
        return obj.assigned_tasks.exclude(status="DONE").count()

    def get_workload_hours(self, obj):
        from django.db.models import Sum
        total = obj.assigned_tasks.exclude(status="DONE").aggregate(
            s=Sum("estimate_hours")
        )["s"]
        return float(total or 0)


class UserListSerializer(serializers.ModelSerializer):
    """Version allégée pour les listes (admin / équipes)."""

    full_name = serializers.CharField(read_only=True)
    initials = serializers.CharField(read_only=True)
    active_tasks = serializers.SerializerMethodField()
    workload_hours = serializers.SerializerMethodField()
    team_names = serializers.SerializerMethodField()
    utilisation = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "initials",
            "role", "status", "job_title", "avatar_color", "company", "is_active",
            "weekly_capacity_hours", "hourly_cost", "active_tasks", "workload_hours",
            "team_names", "utilisation", "last_seen_at", "created_at",
        ]

    def get_active_tasks(self, obj):
        return obj.assigned_tasks.exclude(status="DONE").count()

    def get_workload_hours(self, obj):
        from django.db.models import Sum
        total = obj.assigned_tasks.exclude(status="DONE").aggregate(s=Sum("estimate_hours"))["s"]
        return float(total or 0)

    def get_team_names(self, obj):
        return list(obj.teams.values_list("name", flat=True))

    def get_utilisation(self, obj):
        from django.db.models import Sum
        capacity = float(obj.weekly_capacity_hours or 0)
        if capacity <= 0:
            return 0
        total = obj.assigned_tasks.exclude(status="DONE").aggregate(s=Sum("estimate_hours"))["s"]
        return round(float(total or 0) / capacity * 100, 1)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "password", "password_confirm", "first_name", "last_name",
                  "company", "job_title", "role", "phone"]

    def validate_role(self, value):
        # On ne peut pas s'auto-déclarer administrateur à l'inscription.
        if value == User.Role.ADMIN:
            raise serializers.ValidationError("Le rôle administrateur ne peut pas être choisi à l'inscription.")
        return value or User.Role.PM

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return value.lower()

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Les mots de passe ne correspondent pas."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.status = User.Status.ACTIVE
        user.save()
        return user


class TeamSerializer(serializers.ModelSerializer):
    members = UserListSerializer(many=True, read_only=True)
    member_ids = serializers.PrimaryKeyRelatedField(
        source="members", queryset=User.objects.all(), many=True, write_only=True, required=False
    )
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = ["id", "name", "description", "color", "owner", "owner_name",
                  "members", "member_ids", "member_count", "created_at", "updated_at"]
        read_only_fields = ["id", "owner", "created_at", "updated_at"]

    owner_name = serializers.CharField(source="owner.full_name", read_only=True)

    def get_member_count(self, obj):
        return obj.members.count()


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "job_title", "bio", "company",
                  "avatar_color", "timezone", "locale", "weekly_capacity_hours",
                  "notify_email", "notify_push", "notify_risk_alerts",
                  "notify_assignments", "notify_agent_runs", "notify_weekly_digest"]


class AdminUserWriteSerializer(serializers.ModelSerializer):
    """Création / édition de compte par un administrateur."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "status", "phone",
                  "job_title", "company", "is_active", "is_staff", "avatar_color",
                  "weekly_capacity_hours", "hourly_cost", "password"]

    def validate_email(self, value):
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Cette adresse e-mail est déjà utilisée.")
        return value.lower()

    def create(self, validated_data):
        password = validated_data.pop("password", None) or "Cadria@2026"
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate_old_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(min_length=6, max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])

    def validate(self, attrs):
        try:
            user = User.objects.get(email__iexact=attrs["email"])
        except User.DoesNotExist:
            raise serializers.ValidationError({"email": "Aucun compte associé à cette adresse."})
        code = PasswordResetCode.objects.filter(user=user, code=attrs["code"]).order_by("-created_at").first()
        if not code or not code.is_valid:
            raise serializers.ValidationError({"code": "Code invalide ou expiré."})
        attrs["user"] = user
        attrs["code_obj"] = code
        return attrs
