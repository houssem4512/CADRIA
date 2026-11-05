"""
Jira REST API v3 client with idempotency + rate limiting.

Setup:
  - Integration.api_token = your Jira API token
  - Integration.base_url = https://your-domain.atlassian.net
  - Integration.api_user = your Jira email (stored in metadata JSON)

The client adds an `Idempotency-Key` header to every POST so retries
don't duplicate tickets. Rate limited to 150 req/min (Jira Cloud limit).
"""
from __future__ import annotations
import logging
import time
import uuid
from typing import Any

import httpx

logger = logging.getLogger(__name__)

JIRA_RATE_LIMIT_PER_MIN = 150


class _TokenBucket:
    """Simple token bucket rate limiter — 150 tokens per minute for Jira Cloud."""

    def __init__(self, rate_per_min: int = JIRA_RATE_LIMIT_PER_MIN):
        self.capacity = rate_per_min
        self.tokens = float(rate_per_min)
        self.last_refill = time.monotonic()
        self.rate_per_sec = rate_per_min / 60.0

    def acquire(self, timeout: float = 30.0):
        """Block until a token is available."""
        while True:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)
            self.last_refill = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            time.sleep(min(0.5, timeout))


_bucket = _TokenBucket()


class JiraClient:
    """Minimal Jira Cloud REST v3 client — issues, epics, sprints."""

    def __init__(self, base_url: str, api_token: str, api_user: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.api_user = api_user
        self.calls_made = 0

    def _headers(self, idempotency_key: str | None = None) -> dict:
        import base64
        creds = base64.b64encode(f"{self.api_user}:{self.api_token}".encode()).decode()
        h = {
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotency_key:
            h["Idempotency-Key"] = idempotency_key
        return h

    def _post(self, path: str, body: dict, idempotency_key: str | None = None, retry: int = 1) -> dict:
        _bucket.acquire()
        url = f"{self.base_url}{path}"
        headers = self._headers(idempotency_key or str(uuid.uuid4()))
        last_err = None
        for attempt in range(retry + 1):
            try:
                with httpx.Client(timeout=30) as client:
                    resp = client.post(url, headers=headers, json=body)
                self.calls_made += 1
                if resp.status_code == 429:
                    wait = float(resp.headers.get("retry-after", "2"))
                    logger.warning("Jira rate limited, waiting %ss", wait)
                    time.sleep(wait)
                    continue
                if resp.status_code >= 400:
                    last_err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    if attempt < retry:
                        time.sleep(1.5 * (attempt + 1))
                        continue
                    raise JiraError(last_err)
                return resp.json()
            except httpx.RequestError as e:
                last_err = str(e)
                if attempt < retry:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise JiraError(f"Network error: {e}")
        raise JiraError(last_err or "Unknown Jira error")

    def create_issue(self, project_key: str, summary: str, description: str = "",
                     issue_type: str = "Task", epic_key: str | None = None,
                     assignee_account_id: str | None = None) -> dict:
        """Create a Jira issue (ticket). Returns {key, id, self, ...}."""
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary[:250],
            "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description[:2000]}]}]},
            "issuetype": {"name": issue_type},
        }
        if epic_key:
            fields["parent"] = {"key": epic_key}
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        result = self._post(
            "/rest/api/3/issue",
            {"fields": fields},
            idempotency_key=f"cadria-issue-{uuid.uuid4().hex[:12]}",
        )
        return {
            "external_id": result.get("key"),
            "external_url": f"{self.base_url}/browse/{result.get('key')}",
            "entity": "issue",
            "jira_id": result.get("id"),
        }

    def create_epic(self, project_key: str, name: str, summary: str = "") -> dict:
        """Create an Epic. Jira Cloud uses the 'Epic' issue type."""
        return self.create_issue(
            project_key=project_key,
            summary=name[:250],
            description=summary,
            issue_type="Epic",
        )


class JiraError(Exception):
    pass
