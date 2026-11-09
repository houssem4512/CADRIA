from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AgentDefinitionViewSet,
    AgentMonitorView,
    AgentRunViewSet,
    AssignmentSuggestionViewSet,
    AutoAssignProposalView,
    ProposalViewSet,
    PushProposalToTrelloView,
    RunAgentView,
    ValidateProposalView,
)
from .trello_views import (
    trello_auth_url,
    trello_connect,
    trello_status,
    trello_disconnect,
    trello_boards,
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
    # Agent 2 — push an APPROVED proposal's tasks to Trello on demand
    path("proposals/<int:pk>/push-to-trello/", PushProposalToTrelloView.as_view(), name="proposal-push-trello"),
    # Agent 2 — auto-assign best candidates to unassigned tasks
    path("proposals/<int:pk>/auto-assign/", AutoAssignProposalView.as_view(), name="proposal-auto-assign"),
    # Trello OAuth endpoints
    path("trello/auth-url/", trello_auth_url, name="trello-auth-url"),
    path("trello/connect/", trello_connect, name="trello-connect"),
    path("trello/status/", trello_status, name="trello-status"),
    path("trello/disconnect/", trello_disconnect, name="trello-disconnect"),
    path("trello/boards/", trello_boards, name="trello-boards"),
] + router.urls