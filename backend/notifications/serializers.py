from rest_framework import serializers

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.SerializerMethodField()
    time_ago = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "user", "is_broadcast", "target_role", "category", "level", "title",
            "message", "link", "entity_type", "entity_id", "metadata", "read", "is_read",
            "archived", "starred", "created_at", "time_ago",
        ]
        read_only_fields = ["id", "user", "is_broadcast", "created_at"]

    def get_is_read(self, obj):
        """Pour les diffusions, l'état de lecture est individuel."""
        if not obj.is_broadcast:
            return obj.read
        user = self.context.get("current_user") or self.context.get("request").user
        if not user or not user.is_authenticated:
            return False
        return obj.reads.filter(user=user).exists()

    def get_time_ago(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        delta = timezone.now() - obj.created_at
        if delta < timedelta(minutes=1):
            return "à l'instant"
        if delta < timedelta(hours=1):
            return f"il y a {int(delta.total_seconds() // 60)} min"
        if delta < timedelta(days=1):
            return f"il y a {int(delta.total_seconds() // 3600)} h"
        if delta < timedelta(days=7):
            return f"il y a {delta.days} j"
        return obj.created_at.strftime("%d/%m/%Y")


class BroadcastSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=200)
    message = serializers.CharField(allow_blank=True, required=False, default="")
    level = serializers.ChoiceField(choices=Notification.Level.choices, default=Notification.Level.INFO)
    category = serializers.ChoiceField(choices=Notification.Category.choices, default=Notification.Category.SYSTEM)
    link = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")
    target_role = serializers.ChoiceField(
        choices=[("ALL", "Tous"), ("ADMIN", "Administrateurs"), ("PM", "Chefs de projet"),
                 ("MEMBER", "Membres d'équipe"), ("VIEWER", "Observateurs")],
        required=False, allow_blank=True, default="ALL",
    )
    targets = serializers.ListField(child=serializers.IntegerField(), required=False)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ["in_app", "email", "slack", "digest_frequency", "quiet_hours_start",
                  "quiet_hours_end", "updated_at"]
