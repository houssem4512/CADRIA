from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CommentViewSet,
    IntegrationViewSet,
    ProjectViewSet,
    RiskAlertViewSet,
    SprintViewSet,
    TaskViewSet,
    WorkPackageViewSet,
)

router = DefaultRouter()
router.register(r"projects", ProjectViewSet, basename="project")
router.register(r"work-packages", WorkPackageViewSet, basename="workpackage")
router.register(r"sprints", SprintViewSet, basename="sprint")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"risks", RiskAlertViewSet, basename="risk")
router.register(r"comments", CommentViewSet, basename="comment")
router.register(r"integrations", IntegrationViewSet, basename="integration")

urlpatterns = router.urls
