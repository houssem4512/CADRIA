import os
from unittest.mock import patch

from .seed_helper import seed_demo_data
from django.test import TestCase

from orchestration.models import AgentDefinition, AgentRun, Proposal
from projects.models import Task

from .service import run_ops


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self.payload = payload
        self.content = b"x" if payload else b""
        self.text = ""

    def json(self):
        return self.payload


class FakeJira:
    """Simule l'API Jira : mémorise les appels, renvoie des clés/identifiants incrémentaux."""

    def __init__(self, users):
        self.calls, self.n, self.users = [], 0, users

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url))
        self.n += 1
        if method == "GET" and url.endswith("/board"):
            return FakeResponse({"values": [{"id": 7}]})
        if method == "GET" and "/user/assignable/search" in url:
            return FakeResponse(self.users)
        if method == "POST" and url.endswith("/rest/agile/1.0/sprint"):
            return FakeResponse({"id": 100 + self.n})
        if method == "POST" and url.endswith("/rest/api/2/issue"):
            return FakeResponse({"key": f"PRJ-{self.n}"})
        return FakeResponse({})

    def count(self, method, suffix):
        return sum(1 for m, u in self.calls if m == method and u.endswith(suffix))

    def sprint_adds(self):
        return sum(1 for m, u in self.calls if m == "POST" and "/sprint/" in u and u.endswith("/issue"))


class OpsJiraTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_demo_data()

    def setUp(self):
        for prop in Proposal.objects.all():
            if Task.objects.filter(project=prop.project, external_id="", sprint__isnull=False).exists():
                self.prop = prop
                break
        else:
            self.skipTest("Pas de données de démo exploitables.")
        self.project = self.prop.project
        self.project.external_provider = "JIRA"
        self.project.external_key = "PRJ"
        self.project.save(update_fields=["external_provider", "external_key"])
        self.prop.status = Proposal.Status.APPROVED
        self.prop.save(update_fields=["status"])
        self.agent = AgentDefinition.objects.get(key="OPS")
        users = [{"accountId": f"A{u.pk}", "displayName": u.full_name} for u in self.project.members.all()]
        self.fake = FakeJira(users)

    def _run(self, **extra):
        payload = {"proposal_id": self.prop.pk, "provider": "JIRA", **extra}
        run = AgentRun.objects.create(project=self.project, agent=self.agent, input_payload=payload)
        env = {"JIRA_BASE_URL": "https://exemple.atlassian.net", "JIRA_EMAIL": "a@b.c", "JIRA_API_TOKEN": "x"}
        with patch.dict(os.environ, env), patch("agents.ops.jira_client.requests.request", self.fake):
            run_ops(run)
        run.refresh_from_db()
        return run

    def test_dry_run_n_ecrit_rien(self):
        run = self._run(dry_run=True)
        self.assertEqual(run.status, AgentRun.Status.SUCCEEDED)
        self.assertEqual(self.fake.calls, [])

    def test_push_jira_idempotent(self):
        first = self._run(dry_run=False)
        created = first.output_payload["created"]
        self.assertGreater(len(created), 0)
        self.assertGreaterEqual(self.fake.count("POST", "/rest/api/2/issue"), len(created))
        self.assertEqual(self.fake.sprint_adds(), len(created))      # chaque ticket est mis dans son sprint
        self.assertEqual(self.fake.count("PUT", "/assignee"), len(first.output_payload["assignments"]))
        for entry in created:
            self.assertTrue(Task.objects.get(pk=entry["task_id"]).external_id.startswith("PRJ-"))

        issues_before = self.fake.count("POST", "/rest/api/2/issue")
        self._run(dry_run=False)                                      # deuxième exécution
        self.assertEqual(self.fake.count("POST", "/rest/api/2/issue"), issues_before)   # aucun doublon