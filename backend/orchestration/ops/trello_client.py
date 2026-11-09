"""
Trello REST API v1 client with idempotency + rich card features.

Trello uses query-string auth (?key=...&token=...) instead of headers.
Setup:
  - Integration.workspace = your Trello API token (user-pasted)
  - Integration.board_key = Trello board ID
  - settings.TRELLO_APP_KEY = your app's Trello API key (server-side env)

Features:
  - create_list, create_card (basic)
  - get_board_members (email matching for assignees)
  - add_label_to_card (priority colors)
  - add_member_to_card (assignee)
  - set_card_due_date (due dates)
  - create_checklist (acceptance criteria)
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TrelloClient:
    """Minimal Trello REST v1 client — lists, cards, labels, members, checklists."""

    def __init__(self, api_key: str, api_token: str, base_url: str = "https://api.trello.com"):
        self.api_key = api_key
        self.api_token = api_token
        self.base_url = base_url.rstrip("/")
        self.calls_made = 0

    def _params(self, extra: dict | None = None) -> dict:
        p = {"key": self.api_key, "token": self.api_token}
        if extra:
            p.update(extra)
        return p

    def _post(self, path: str, body: dict | None = None, params: dict | None = None, retry: int = 1) -> dict:
        url = f"{self.base_url}{path}"
        body = body or {}
        body["idempotencyKey"] = f"cadria-{uuid.uuid4().hex[:12]}"
        last_err = None
        for attempt in range(retry + 1):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(url, params=self._params(params), json=body)
                self.calls_made += 1
                if resp.status_code == 429:
                    wait = float(resp.headers.get("retry-after", "2"))
                    logger.warning("Trello rate limited, waiting %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if attempt < retry:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise TrelloError(last_err)
                return resp.json()
            except httpx.RequestError as e:
                last_err = str(e)
                if attempt < retry:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise TrelloError(f"Network error: {e}")
        raise TrelloError(last_err or "Unknown Trello error")

    def _get(self, path: str, params: dict | None = None, retry: int = 1) -> Any:
        url = f"{self.base_url}{path}"
        last_err = None
        for attempt in range(retry + 1):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.get(url, params=self._params(params))
                self.calls_made += 1
                if resp.status_code == 429:
                    wait = float(resp.headers.get("retry-after", "2"))
                    logger.warning("Trello rate limited, waiting %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if attempt < retry:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise TrelloError(last_err)
                return resp.json()
            except httpx.RequestError as e:
                last_err = str(e)
                if attempt < retry:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise TrelloError(f"Network error: {e}")
        raise TrelloError(last_err or "Unknown Trello error")

    def _put(self, path: str, body: dict | None = None, params: dict | None = None, retry: int = 1) -> dict:
        url = f"{self.base_url}{path}"
        body = body or {}
        last_err = None
        for attempt in range(retry + 1):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.put(url, params=self._params(params), json=body)
                self.calls_made += 1
                if resp.status_code == 429:
                    wait = float(resp.headers.get("retry-after", "2"))
                    logger.warning("Trello rate limited, waiting %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if attempt < retry:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise TrelloError(last_err)
                return resp.json()
            except httpx.RequestError as e:
                last_err = str(e)
                if attempt < retry:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise TrelloError(f"Network error: {e}")
        raise TrelloError(last_err or "Unknown Trello error")

    # ------------------------------------------------------------------
    # Basic operations (preserved from original)
    # ------------------------------------------------------------------
    def create_list(self, board_id: str, name: str) -> dict:
        """Create a Trello list."""
        result = self._post(f"/1/boards/{board_id}/lists", {"name": name[:50]})
        return {
            "external_id": result.get("id"),
            "external_url": f"{self.base_url}/b/{board_id}",
            "entity": "list",
        }

    def create_card(self, list_id: str, name: str, description: str = "") -> dict:
        """Create a Trello card."""
        result = self._post("/1/cards", {"idList": list_id, "name": name[:150], "desc": description[:2000]})
        return {
            "external_id": result.get("id"),
            "external_url": result.get("url", ""),
            "entity": "card",
        }

    # ------------------------------------------------------------------
    # NEW: Member lookup for assignee matching
    # ------------------------------------------------------------------
    def get_board_members(self, board_id: str) -> list[dict]:
        """List members of a Trello board (for email-based assignee matching).

        Returns a list of dicts: [{"id": "...", "fullName": "...", "username": "...", "email": "..."}].
        Note: email is only returned if the token belongs to the board admin or self.
        """
        try:
            members = self._get(
                f"/1/boards/{board_id}/members",
                params={"fields": "fullName,username,email"},
            )
            return [
                {
                    "id": m.get("id"),
                    "fullName": m.get("fullName", ""),
                    "username": m.get("username", ""),
                    "email": m.get("email", "") or "",
                }
                for m in (members or [])
            ]
        except TrelloError as e:
            logger.warning("Failed to list board members: %s", e)
            return []

    def get_member_details(self, member_id: str) -> dict:
        """Get a member's details (including email if visible)."""
        try:
            m = self._get(
                f"/1/members/{member_id}",
                params={"fields": "fullName,username,email"},
            )
            return {
                "id": m.get("id"),
                "fullName": m.get("fullName", ""),
                "username": m.get("username", ""),
                "email": m.get("email", "") or "",
            }
        except TrelloError as e:
            logger.warning("Failed to get member %s: %s", member_id, e)
            return {}

    # ------------------------------------------------------------------
    # NEW: Card enrichment — labels, members, due dates, checklists
    # ------------------------------------------------------------------
    def add_label_to_card(self, card_id: str, color: str) -> bool:
        """Add a color label to a card. Valid colors:
        red, yellow, green, blue, purple, orange, pink, sky, lime, black
        """
        try:
            self._post(f"/1/cards/{card_id}/labels", {"color": color, "name": ""})
            return True
        except TrelloError as e:
            logger.warning("Failed to add label %s to card %s: %s", color, card_id, e)
            return False

    def add_named_label_to_card(self, card_id: str, color: str, name: str) -> bool:
        """Add a named colored label to a card (creates label if needed)."""
        try:
            self._post(f"/1/cards/{card_id}/labels", {"color": color, "name": name[:30]})
            return True
        except TrelloError as e:
            logger.warning("Failed to add named label to card %s: %s", card_id, e)
            return False

    def add_member_to_card(self, card_id: str, member_id: str) -> bool:
        """Assign a Trello member to a card."""
        try:
            self._post(
                f"/1/cards/{card_id}/idMembers",
                params={"value": member_id},
            )
            return True
        except TrelloError as e:
            logger.warning("Failed to add member %s to card %s: %s", member_id, card_id, e)
            return False

    def set_card_due_date(self, card_id: str, due_date: str) -> bool:
        """Set the due date on a card. due_date must be ISO 8601 (e.g. '2026-12-31T23:59:59.000Z')."""
        try:
            self._put(
                f"/1/cards/{card_id}",
                params={"due": due_date},
            )
            return True
        except TrelloError as e:
            logger.warning("Failed to set due date on card %s: %s", card_id, e)
            return False

    def create_checklist(self, card_id: str, name: str, items: list[str]) -> bool:
        """Create a checklist with items on a card. Returns True on success."""
        if not items:
            return True
        try:
            # Create the checklist
            result = self._post(f"/1/cards/{card_id}/checklists", {"name": name[:50]})
            checklist_id = result.get("id")
            if not checklist_id:
                return False
            # Add items one by one (Trello API doesn't support batch)
            for item in items[:20]:  # cap at 20 items
                try:
                    self._post(
                        f"/1/checklists/{checklist_id}/checkItems",
                        {"name": item[:150], "checked": False},
                    )
                except TrelloError as e:
                    logger.warning("Failed to add checkitem '%s': %s", item[:30], e)
            return True
        except TrelloError as e:
            logger.warning("Failed to create checklist on card %s: %s", card_id, e)
            return False


class TrelloError(Exception):
    pass
