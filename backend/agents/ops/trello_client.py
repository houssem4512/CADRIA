import os
import time

import requests

from .base import ProviderClient

BASE = "https://api.trello.com/1"


class TrelloClient(ProviderClient):
    def __init__(self, board_id: str = "", dry_run: bool = True):
        super().__init__(dry_run)
        self.board_id = board_id
        self.key = os.environ.get("TRELLO_KEY", "")
        self.token = os.environ.get("TRELLO_TOKEN", "")

    def _request(self, method: str, path: str, retries: int = 4, **params) -> dict:
        if self.dry_run:
            return {"id": f"dry-{method}-{path}", "url": "", "dry_run": True}
        params.update(key=self.key, token=self.token)
        for attempt in range(retries):
            resp = requests.request(method, f"{BASE}{path}", params=params, timeout=15)
            self.api_calls += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                time.sleep(2 ** attempt)  # backoff exponentiel
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"Trello indisponible après {retries} tentatives : {path}")

    def create_sprint(self, name: str, goal: str = "") -> dict:
        # Un sprint = une liste Trello
        return self._request("POST", "/lists", name=name, idBoard=self.board_id)

    def create_task(self, container_id: str, task: dict) -> dict:
        return self._request(
            "POST", "/cards",
            idList=container_id, name=task["title"], desc=task.get("description", ""),
        )

    def assign(self, external_task_id: str, member_id: str) -> dict:
        return self._request("POST", f"/cards/{external_task_id}/idMembers", value=member_id)