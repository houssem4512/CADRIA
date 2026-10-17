"""Client Jira Cloud (REST v2 + Agile 1.0) : sprints, epics, tickets, assignation."""
import os
import time

import requests

from .base import ProviderClient

PRIORITY = {"LOWEST": "Lowest", "LOW": "Low", "MEDIUM": "Medium", "HIGH": "High", "HIGHEST": "Highest"}
ISSUE_TYPE = {"BUG": "Bug", "FEATURE": "Story"}   # tout le reste -> "Task"


class JiraClient(ProviderClient):
    def __init__(self, project_key: str = "", dry_run: bool = True):
        super().__init__(dry_run)
        self.project_key = project_key
        self.base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
        self.auth = (os.environ.get("JIRA_EMAIL", ""), os.environ.get("JIRA_API_TOKEN", ""))
        self.points_field = os.environ.get("JIRA_STORY_POINTS_FIELD", "")   # ex. customfield_10016
        self.epic_name_field = os.environ.get("JIRA_EPIC_NAME_FIELD", "")   # ex. customfield_10011
        self._board_id = None
        self._dry_count = 0

    def _request(self, method, path, params=None, body=None, retries=4):
        if self.dry_run:
            self._dry_count += 1
            return {"id": f"dry-{self._dry_count}", "key": f"DRY-{self._dry_count}", "dry_run": True}
        for attempt in range(retries):
            resp = requests.request(
                method, f"{self.base_url}{path}", params=params, json=body,
                auth=self.auth, headers={"Accept": "application/json"}, timeout=15,
            )
            self.api_calls += 1
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = resp.headers.get("Retry-After", "")
                time.sleep(min(int(wait) if wait.isdigit() else 2 ** attempt, 30))
                continue
            if resp.status_code >= 400:
                raise RuntimeError(f"Jira {resp.status_code} sur {method} {path} : {resp.text[:200]}")
            return resp.json() if resp.content else {}
        raise RuntimeError(f"Jira indisponible après {retries} tentatives : {path}")

    def _url(self, key):
        return f"{self.base_url}/browse/{key}"

    def _scrum_board(self):
        if self._board_id is None:
            data = self._request("GET", "/rest/agile/1.0/board",
                                 params={"projectKeyOrId": self.project_key, "type": "scrum"})
            boards = data.get("values", [])
            if not boards:
                raise RuntimeError(f"Aucun board Scrum pour le projet Jira {self.project_key}")
            self._board_id = boards[0]["id"]
        return self._board_id

    def create_sprint(self, name: str, goal: str = "") -> dict:
        board = None if self.dry_run else self._scrum_board()
        data = self._request("POST", "/rest/agile/1.0/sprint",
                             body={"name": name, "goal": goal, "originBoardId": board})
        return {"id": str(data["id"]), "url": ""}

    def create_epic(self, name: str, description: str = ""):
        fields = {
            "project": {"key": self.project_key},
            "summary": name,
            "description": description,
            "issuetype": {"name": "Epic"},
        }
        if self.epic_name_field:
            fields[self.epic_name_field] = name
        data = self._request("POST", "/rest/api/2/issue", body={"fields": fields})
        return {"id": data["key"], "url": self._url(data["key"])}

    def create_task(self, container_id: str, task: dict) -> dict:
        fields = {
            "project": {"key": self.project_key},
            "summary": task["title"],
            "description": task.get("description", ""),
            "issuetype": {"name": ISSUE_TYPE.get(task.get("type"), "Task")},
            "labels": [s.replace(" ", "-") for s in task.get("skills") or []],
        }
        if task.get("priority") in PRIORITY:
            fields["priority"] = {"name": PRIORITY[task["priority"]]}
        if task.get("epic_id"):
            fields["parent"] = {"key": task["epic_id"]}
        if self.points_field and task.get("story_points"):
            fields[self.points_field] = float(task["story_points"])

        data = self._request("POST", "/rest/api/2/issue", body={"fields": fields})
        key = data["key"]
        if container_id:
            self._request("POST", f"/rest/agile/1.0/sprint/{container_id}/issue", body={"issues": [key]})
        return {"id": key, "url": self._url(key)}

    def assign(self, external_task_id: str, member_id: str) -> dict:
        return self._request("PUT", f"/rest/api/2/issue/{external_task_id}/assignee",
                             body={"accountId": member_id})

    def list_members(self) -> list:
        if self.dry_run:
            return []
        users = self._request("GET", "/rest/api/2/user/assignable/search",
                              params={"project": self.project_key, "maxResults": 100})
        return [{"id": u["accountId"], "fullName": u.get("displayName", "")} for u in users]