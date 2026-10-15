from unittest.mock import patch

from .seed_helper import seed_demo_data
from django.test import TestCase

from orchestration.models import AgentDefinition, AgentRun, Proposal
from projects.models import Task

from .service import run_ops


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeTrello:
    """Simule l'API Trello : mémorise les appels et renvoie des identifiants incrémentaux."""

    def __init__(self, members):
        self.calls, self.n, self.members = [], 0, members

    def __call__(self, method, url, params=None, timeout=None):
        self.calls.append((method, url))
        self.n += 1
        if method == "GET" and url.endswith("/members"):
            return FakeResponse(self.members)
        if url.endswith("/cards"):
            return FakeResponse({"id": f"C{self.n}", "url": f"https://trello.test/c/{self.n}"})
        return FakeResponse({"id": f"X{self.n}"})

    def count(self, method, suffix):
        return sum(1 for m, u in self.calls if m == method and u.endswith(suffix))


class OpsPushTests(TestCase):
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
        self.project.external_key = "board-test"
        self.project.save(update_fields=["external_key"])
        self.agent = AgentDefinition.objects.get(key="OPS")
        members = [{"id": f"M{u.pk}", "fullName": u.full_name} for u in self.project.members.all()]
        self.fake = FakeTrello(members)

    def _run(self, **extra):
        payload = {"proposal_id": self.prop.pk, "provider": "TRELLO", **extra}
        run = AgentRun.objects.create(project=self.project, agent=self.agent, input_payload=payload)
        with patch("agents.ops.trello_client.requests.request", self.fake):
            run_ops(run)
        run.refresh_from_db()
        return run

    def test_refuse_sans_validation_humaine(self):
        self.prop.status = "DRAFT"
        self.prop.save(update_fields=["status"])
        run = self._run(dry_run=False)
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertEqual(self.fake.calls, [])          # aucune écriture

    def test_dry_run_n_ecrit_rien(self):
        run = self._run(dry_run=True)
        self.assertEqual(run.status, AgentRun.Status.SUCCEEDED)
        self.assertEqual(self.fake.calls, [])

    def test_push_idempotent(self):
        self.prop.status = Proposal.Status.APPROVED
        self.prop.save(update_fields=["status"])

        first = self._run(dry_run=False)
        cards_1 = self.fake.count("POST", "/cards")
        self.assertGreater(cards_1, 0)
        self.assertEqual(cards_1, len(first.output_payload["created"]))
        self.assertEqual(self.fake.count("POST", "/idMembers"), len(first.output_payload["assignments"]))
        for entry in first.output_payload["created"]:
            self.assertEqual(Task.objects.get(pk=entry["task_id"]).external_id, entry["external_id"])

        self._run(dry_run=False)                        # deuxième exécution
        self.assertEqual(self.fake.count("POST", "/cards"), cards_1)   # aucun doublon