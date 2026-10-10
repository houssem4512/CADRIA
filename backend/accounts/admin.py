from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Skill, UserSkill, Team, PasswordResetCode


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "full_name_display", "role", "status", "is_active", "created_at")
    list_filter = ("role", "status", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Identité", {"fields": ("first_name", "last_name", "job_title", "phone", "avatar_color")}),
        ("Plateforme", {"fields": ("role", "status", "company", "timezone", "locale")}),
        ("Capacité", {"fields": ("weekly_capacity_hours", "hourly_cost")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "last_seen_at", "created_at")}),
    )
    readonly_fields = ("last_login", "last_seen_at", "created_at")
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "first_name", "last_name", "role", "password1", "password2")}),
    )

    @admin.display(description="Nom")
    def full_name_display(self, obj):
        return obj.full_name


admin.site.register(Skill)
admin.site.register(UserSkill)
admin.site.register(Team)
admin.site.register(PasswordResetCode)
