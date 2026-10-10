"""
URLs de l'API Cadria.
"""
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt


def api_root(request):
    return JsonResponse({
        "name": "Cadria API",
        "description": "Copilote de cadrage, de découpage et de pilotage de projets",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth/",
            "users": "/api/users/",
            "teams": "/api/teams/",
            "skills": "/api/skills/",
            "projects": "/api/projects/",
            "tasks": "/api/tasks/",
            "sprints": "/api/sprints/",
            "work-packages": "/api/work-packages/",
            "risks": "/api/risks/",
            "comments": "/api/comments/",
            "integrations": "/api/integrations/",
            "agents": "/api/agents/",
            "proposals": "/api/proposals/",
            "assignments": "/api/assignments/",
            "notifications": "/api/notifications/",
            "analytics": "/api/analytics/",
            "audit": "/api/audit/",
            "admin": "/admin/",
        },
    })


urlpatterns = [
    path("", api_root, name="api-root"),
    path("admin/", admin.site.urls),
    path("api/health/", lambda r: JsonResponse({"status": "ok", "service": "cadria-api"}), name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("accounts.urls_extra")),
    path("api/", include("projects.urls")),
    path("api/", include("orchestration.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("analytics.urls")),
    path("api/", include("audit.urls")),
]
