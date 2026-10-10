from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor_display = serializers.CharField(read_only=True)
    actor_initials = serializers.CharField(source="actor.initials", read_only=True)
    actor_color = serializers.CharField(source="actor.avatar_color", read_only=True)
    action_label = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = AuditLog
        fields = ["id", "actor", "actor_display", "actor_initials", "actor_color",
                  "actor_label", "action", "action_label", "severity", "entity_type",
                  "entity_id", "entity_label", "description", "changes", "metadata",
                  "agent_key", "run", "correlation_id", "ip_address", "created_at"]
        read_only_fields = ["id", "created_at"]
