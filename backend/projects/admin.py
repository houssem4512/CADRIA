from django.contrib import admin
from .models import Comment, Integration, Project, RiskAlert, Sprint, Task, WorkPackage


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("reference", "name", "owner", "status", "health", "progress", "risk_score")
    list_filter = ("status", "health", "methodology")
    search_fields = ("name", "reference", "summary")
    readonly_fields = ("reference", "created_at", "updated_at")


admin.site.register(WorkPackage)
admin.site.register(Sprint)
admin.site.register(Task)
admin.site.register(RiskAlert)
admin.site.register(Integration)
admin.site.register(Comment)
