"""
Trello OAuth integration views.

Endpoints:
  GET  /api/trello/auth-url/          → returns Trello authorization URL
  POST /api/trello/connect/           → stores token + board_id → creates Integration
  GET  /api/trello/status/?project=N  → returns { connected, board_name }
  POST /api/trello/disconnect/        → removes Trello integration
  GET  /api/trello/boards/            → lists user's Trello boards (requires token)
"""
import os
import logging
from django.conf import settings
from django.http import JsonResponse
from rest_framework import status as http_status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from projects.models import Integration

logger = logging.getLogger(__name__)

# The app's Trello API key — get it once from https://trello.com/power-ups/admin
# Store in .env: TRELLO_APP_KEY=your_app_key_here
TRELLO_APP_KEY = os.environ.get("TRELLO_APP_KEY", "")


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trello_auth_url(request):
    """
    Returns the Trello authorization URL.
    The user visits this URL, authorizes Cadria, and gets a token.
    """
    if not TRELLO_APP_KEY:
        return Response({
            "error": "TRELLO_APP_KEY not configured. Add it to backend/.env"
        }, status=http_status.HTTP_400_BAD_REQUEST)

    # Trello's authorization URL
    auth_url = (
        f"https://trello.com/1/authorize?"
        f"expiration=30days&name=Cadria&scope=read,write&response_type=token"
        f"&key={TRELLO_APP_KEY}"
    )

    return Response({
        "auth_url": auth_url,
        "instructions": "Open this URL, authorize Cadria, copy the token, then POST to /api/trello/connect/",
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trello_connect(request):
    """
    Stores the Trello token + board_id for the current user + project.
    Creates or updates an Integration record.

    Body:
    {
        "project": 9,
        "token": "user_trello_token",
        "board_id": "board123",
        "board_name": "My Cadria Board"
    }
    """
    project_id = request.data.get("project")
    token = request.data.get("token", "").strip()
    board_id = request.data.get("board_id", "").strip()
    board_name = request.data.get("board_name", "Trello Board")

    if not token or not board_id:
        return Response({
            "error": "token and board_id are required"
        }, status=http_status.HTTP_400_BAD_REQUEST)

    # Verify the token works by listing boards
    try:
        import httpx
        resp = httpx.get(
            f"https://api.trello.com/1/boards/{board_id}",
            params={"key": TRELLO_APP_KEY, "token": token},
            timeout=10,
        )
        if resp.status_code == 200:
            board_data = resp.json()
            board_name = board_data.get("name", board_name)
        elif resp.status_code == 401:
            return Response({
                "error": "Invalid Trello token. Please re-authorize."
            }, status=http_status.HTTP_401_UNAUTHORIZED)
        else:
            return Response({
                "error": f"Trello API error: HTTP {resp.status_code}"
            }, status=http_status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.warning(f"Trello connection test failed: {e}")
        # Continue anyway — might be a network issue

    # Create or update the Integration
    integration, created = Integration.objects.update_or_create(
        project_id=project_id if project_id else None,
        owner=request.user,
        provider="TRELLO",
        defaults={
            "name": board_name,
            "base_url": "https://api.trello.com",
            "board_key": board_id,
            "workspace": token,  # Store token in workspace field
            "status": "CONNECTED",
            "last_error": "",
        },
    )

    return Response({
        "id": integration.id,
        "connected": True,
        "board_name": board_name,
        "board_id": board_id,
        "provider": "TRELLO",
        "created": created,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trello_status(request):
    """
    Returns the Trello connection status for a project.
    """
    project_id = request.query_params.get("project")

    try:
        integration = Integration.objects.get(
            project_id=project_id,
            provider="TRELLO",
        )
        return Response({
            "connected": integration.status == "CONNECTED",
            "board_name": integration.name,
            "board_id": integration.board_key,
            "status": integration.status,
            "last_error": integration.last_error,
        })
    except Integration.DoesNotExist:
        return Response({
            "connected": False,
            "board_name": None,
            "board_id": None,
            "status": "DISCONNECTED",
            "last_error": "",
        })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def trello_disconnect(request):
    """
    Disconnects Trello for a project.
    """
    project_id = request.data.get("project")
    deleted, _ = Integration.objects.filter(
        project_id=project_id,
        provider="TRELLO",
    ).delete()

    return Response({
        "disconnected": deleted > 0,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def trello_boards(request):
    """
    Lists the user's Trello boards (requires a valid token).
    Query param: ?token=user_trello_token
    """
    token = request.query_params.get("token", "").strip()

    if not token:
        return Response({"error": "token query param required"}, status=400)

    if not TRELLO_APP_KEY:
        return Response({"error": "TRELLO_APP_KEY not configured"}, status=400)

    try:
        import httpx
        resp = httpx.get(
            "https://api.trello.com/1/members/me/boards",
            params={"key": TRELLO_APP_KEY, "token": token, "fields": "name,id"},
            timeout=10,
        )
        if resp.status_code == 200:
            boards = resp.json()
            return Response({
                "boards": [{"id": b["id"], "name": b["name"]} for b in boards],
            })
        else:
            return Response({
                "error": f"Trello API error: HTTP {resp.status_code}"
            }, status=400)
    except Exception as e:
        return Response({"error": str(e)}, status=500)