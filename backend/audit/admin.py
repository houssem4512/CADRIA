from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_display", "action", "entity_type", "agent_key", "severity")
    list_filter = ("action", "severity", "agent_key")
    search_fields = ("description", "entity_label", "actor_label")
    readonly_fields = ("created_at",)
