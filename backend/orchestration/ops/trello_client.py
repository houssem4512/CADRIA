"""
Trello REST API v1 client with idempotency.

Trello uses query-string auth (?key=...&token=...) instead of headers.
Setup:
  - Integration.api_token = your Trello API token
  - Integration.base_url = https://api.trello.com (default)
  - Integration.api_user = your Trello API key (stored in metadata JSON)
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class TrelloClient:
    """Minimal Trello REST v1 client — lists + cards."""

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

    def create_list(self, board_id: str, name: str) -> dict:
        """Create a Trello list (used as a 'sprint' equivalent)."""
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


class TrelloError(Exception):
    pass
