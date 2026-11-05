"""Routes 'espace utilisateur' & administration des comptes."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AdminUserViewSet,
    MeView,
    MemberDirectoryView,
    MySkillsView,
    SkillViewSet,
    TeamViewSet,
)

router = DefaultRouter()
router.register(r"users", AdminUserViewSet, basename="user")
router.register(r"teams", TeamViewSet, basename="team")
router.register(r"skills", SkillViewSet, basename="skill")

urlpatterns = router.urls + [
    path("me/", MeView.as_view(), name="me"),
    path("me/skills/", MySkillsView.as_view(), name="my-skills"),
    path("members/", MemberDirectoryView.as_view(), name="members"),
]
