from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentDefinitionViewSet,
    AgentMonitorView,
    AgentRunViewSet,
    AssignmentSuggestionViewSet,
    ProposalViewSet,
    RunAgentView,
    ValidateProposalView,
)

router = DefaultRouter()
router.register(r"agents", AgentDefinitionViewSet, basename="agent")
router.register(r"agent-runs", AgentRunViewSet, basename="agentrun")
router.register(r"proposals", ProposalViewSet, basename="proposal")
router.register(r"assignments", AssignmentSuggestionViewSet, basename="assignment")

# Les routes littérales doivent précéder le routeur (sinon `agents/monitor/`
# est capturé par la route de détail `agents/<pk>/`).
urlpatterns = [
    path("agents/runs/start/", RunAgentView.as_view(), name="agent-run-start"),
    path("agents/monitor/", AgentMonitorView.as_view(), name="agent-monitor"),
    path("proposals/<int:pk>/validate/", ValidateProposalView.as_view(), name="proposal-validate"),
] + router.urls
