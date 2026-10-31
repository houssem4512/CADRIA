"""Tests du runtime d'agents : moteurs, orchestration et effets de bord."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Skill, UserSkill
from audit.models import AuditLog
from notifications.models import Notification
from projects.models import Comment, Project, RiskAlert, Sprint, Task

from .engines import execute, run_ops, run_risk, run_scoping
from .models import AgentDefinition, AgentRun, AssignmentSuggestion, Proposal

User = get_user_model()
PASSWORD = "Test@2026"

RUNTIME = {
    "ENABLED": True,
    "MODE": "LOCAL",
    "SCOPING_ENDPOINT": "",
    "OPS_ENDPOINT": "",
    "RISK_ENDPOINT": "",
    "ORCHESTRATOR": "CadriaRuntime",
    "HTTP_TIMEOUT": 30,
}

TEAM = [
    {"id": 1, "name": "Alice", "role": "MEMBER", "capacity_hours": 35,
     "skills": [{"name": "React", "level": 5}, {"name": "TypeScript", "level": 4}]},
    {"id": 2, "name": "Bob", "role": "MEMBER", "capacity_hours": 35,
     "skills": [{"name": "Python", "level": 4}, {"name": "Django", "level": 4}]},
]

BRIEF = (
    "Refonte d'un portail client React avec API REST Django, authentification SSO Keycloak, "
    "tableau de bord de reporting, application mobile hors ligne et campagne de recette. "
    "L'équipe dispose de deux développeurs et d'un QA pour une échéance à six mois."
)


class ScopingEngineTests(SimpleTestCase):
    def test_produit_un_plan_structure_et_coherent(self):
        result = run_scoping({
            "brief": BRIEF, "project_reference": "PRJ-0001", "methodology": "SCRUM",
            "constraints": {"budget": 200000, "deadline": (date.today() + timedelta(days=180)).isoformat()},
            "team": TEAM,
        })
        self.assertTrue(result["lots"])
        self.assertTrue(result["tasks"])
        self.assertTrue(result["sprints"])
        self.assertGreater(result["total_estimate_hours"], 0)
        self.assertGreater(result["confidence"], 0)
        names = {lot["name"] for lot in result["lots"]}
        self.assertIn("Front-end & interfaces", names)
        self.assertIn("Back-end & API", names)
        self.assertIn("Authentification & sécurité", names)
        for task in result["tasks"]:
            self.assertIn(task["lot"], names)
            self.assertTrue(task["ref"].startswith("T-"))
            self.assertIn(task["type"], {"FEATURE", "BUG", "TECH", "SPIKE", "DOC", "TEST"})
        total_tasks = round(sum(t["estimate_hours"] for t in result["tasks"]), 1)
        self.assertAlmostEqual(total_tasks, result["total_estimate_hours"], places=1)

    def test_brief_vide_utilise_un_plan_generique(self):
        result = run_scoping({"brief": "", "team": []})
        self.assertEqual([lot["name"] for lot in result["lots"]],
                         ["Cadrage & gouvernance", "Réalisation & fonctionnalités",
                          "Mise en production"])
        self.assertTrue(any(r["category"] == "LOAD" for r in result["risks"]))

    def test_enveloppe_normalisee(self):
        data = execute("SCOPING", {"brief": BRIEF, "team": TEAM})
        self.assertEqual(data["status"], "SUCCEEDED")
        self.assertIn("tasks", data["output"])
        self.assertGreaterEqual(data["latency_ms"], 0)

    def test_agent_inconnu_echoue_proprement(self):
        data = execute("NOPE", {})
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("Aucun moteur", data["error"])


class OpsEngineTests(SimpleTestCase):
    def test_suggestions_par_competences_et_charge(self):
        result = run_ops({
            "provider": "JIRA", "dry_run": True, "team": TEAM,
            "tasks": [
                {"ref": "T-001", "title": "Écran React", "estimate_hours": 40, "skills": ["React"]},
                {"ref": "T-002", "title": "Endpoint Django", "estimate_hours": 32, "skills": ["Django"]},
            ],
            "assignments": [],
        })
        self.assertEqual(len(result["suggestions"]), 2)
        first = result["suggestions"][0]
        self.assertEqual(first["task_ref"], "T-001")
        self.assertEqual(first["user_id"], 1)
        second = result["suggestions"][1]
        self.assertEqual(second["user_id"], 2)
        self.assertGreater(first["match_score"], 0)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["created"], [])

    def test_plan_vide_renvoie_un_echec_explicite(self):
        data = execute("OPS", {"tasks": []})
        self.assertEqual(data["status"], "FAILED")
        self.assertIn("Aucune tâche", data["error"])


class RiskEngineTests(SimpleTestCase):
    def test_detecte_blocages_retards_et_signaux_faibles(self):
        tasks = [
            {"id": 1, "title": "Tâche bloquée", "status": "BLOCKED", "blocked": True,
             "estimate_hours": 20, "spent_hours": 5, "due_date": None, "risk_score": 80},
            {"id": 2, "title": "Tâche en retard", "status": "IN_PROGRESS", "blocked": False,
             "estimate_hours": 10, "spent_hours": 18,
             "due_date": (date.today() - timedelta(days=4)).isoformat(), "risk_score": 55},
        ]
        comments = [
            {"id": 1, "body": "Je suis bloqué en attente de la validation ERP."},
            {"id": 2, "body": "Une régression est apparue depuis la dernière release."},
        ]
        result = run_risk({"tasks": tasks, "comments": comments, "window_days": 30})
        categories = {a["category"] for a in result["alerts"]}
        self.assertIn("BLOCKER", categories)
        self.assertIn("DELAY", categories)
        self.assertIn("QUALITY", categories)
        self.assertGreater(result["risk_score"], 30)
        self.assertTrue(result["factors"])


@override_settings(AGENT_RUNTIME=RUNTIME)
class DispatchIntegrationTests(TestCase):
    def setUp(self):
        self.pm = User.objects.create_user(
            email="pm-runtime@test.io", password=PASSWORD,
            first_name="Pm", last_name="Runtime", role=User.Role.PM,
            status=User.Status.ACTIVE, is_active=True, weekly_capacity_hours=35,
        )
        self.member = User.objects.create_user(
            email="member-runtime@test.io", password=PASSWORD,
            first_name="Mem", last_name="Ber", role=User.Role.MEMBER,
            status=User.Status.ACTIVE, is_active=True, weekly_capacity_hours=35,
        )
        skill = Skill.objects.create(name="React", category="TECH")
        UserSkill.objects.create(user=self.member, skill=skill, level=5)
        self.project = Project.objects.create(owner=self.pm, name="Portail runtime", brief=BRIEF)
        self.project.members.add(self.pm, self.member)
        self.agent = AgentDefinition.objects.create(
            key=AgentDefinition.Kind.SCOPING, name="Agent Scoping",
            short_name="Scoping", state=AgentDefinition.State.ENABLED,
            requires_human_validation=True,
        )
        self.ops = AgentDefinition.objects.create(
            key=AgentDefinition.Kind.OPS, name="Agent Ops",
            short_name="Ops", state=AgentDefinition.State.ENABLED,
        )
        self.risk = AgentDefinition.objects.create(
            key=AgentDefinition.Kind.RISK, name="Agent Risk",
            short_name="Risk", state=AgentDefinition.State.ENABLED,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.pm)

    def _launch(self, key, payload=None):
        return self.client.post("/api/agents/runs/start/", {
            "project": self.project.pk, "agent": key, "input": payload or {},
        }, format="json")

    def test_flux_complet_scoping_validation_ops_risk(self):
        res = self._launch("SCOPING")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        self.assertFalse(res.data["reserved"])
        run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(run.status, AgentRun.Status.AWAITING_VALIDATION)
        self.assertTrue(run.output_payload["tasks"])
        proposal = Proposal.objects.get(run=run)
        self.assertEqual(proposal.status, Proposal.Status.PENDING)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.AGENT_RUN).exists())
        self.assertTrue(Notification.objects.filter(user=self.pm).exists())

        res = self.client.post(f"/api/proposals/{proposal.pk}/validate/", {
            "decision": "APPROVE", "create_tasks": True,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertGreater(res.data["created_tasks"], 0)
        self.assertTrue(self.project.tasks.exists())

        res = self._launch("OPS", {"proposal_id": proposal.pk, "dry_run": True})
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        ops_run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(ops_run.status, AgentRun.Status.SUCCEEDED)
        self.assertTrue(AssignmentSuggestion.objects.filter(proposal=proposal).exists())

        task = self.project.tasks.first()
        task.blocked = True
        task.status = Task.Status.BLOCKED
        task.save(update_fields=["blocked", "status"])
        before = RiskAlert.objects.count()
        res = self._launch("RISK", {"window_days": 30})
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        risk_run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(risk_run.status, AgentRun.Status.SUCCEEDED)
        self.assertGreater(RiskAlert.objects.count(), before)
        self.project.refresh_from_db()
        self.assertGreater(float(self.project.risk_score), 0)

    def test_ops_sans_proposition_echoue_sans_crash(self):
        res = self._launch("OPS")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(run.status, AgentRun.Status.FAILED)
        self.assertIn("Aucune proposition", run.error_message)

    def test_mode_http_sans_endpoint_est_ignore_proprement(self):
        with override_settings(AGENT_RUNTIME={**RUNTIME, "MODE": "HTTP"}):
            res = self._launch("SCOPING")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(run.status, AgentRun.Status.SKIPPED)
        self.assertIn("runtime_endpoint", run.error_message)

    # ── Tests de régression pour les correctifs appliqués ──────────────────

    def test_validation_cree_les_sprints_depuis_sprints_payload(self):
        """Régression : _materialise() doit créer les sprints proposés en base.

        Avant le correctif, sprint_by_name était construit depuis les sprints
        déjà en DB ; les sprints du payload n'étaient jamais créés, ce qui
        laissait toutes les tâches avec sprint=None.
        """
        res = self._launch("SCOPING")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        run = AgentRun.objects.get(pk=res.data["run"]["id"])
        proposal = Proposal.objects.get(run=run)

        # Le moteur doit toujours produire au moins un sprint
        self.assertTrue(
            proposal.sprints_payload,
            "Le moteur Scoping n'a produit aucun sprint dans sprints_payload.",
        )

        # Approuver la proposition avec création des tâches
        res = self.client.post(
            f"/api/proposals/{proposal.pk}/validate/",
            {"decision": "APPROVE", "create_tasks": True},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)

        # Tous les sprints proposés doivent exister en base
        sprint_names = {s["name"] for s in proposal.sprints_payload}
        db_sprint_names = set(
            self.project.sprints.values_list("name", flat=True)
        )
        for name in sprint_names:
            self.assertIn(
                name, db_sprint_names,
                f"Sprint '{name}' présent dans sprints_payload mais absent en base.",
            )

        # Au moins une tâche doit être rattachée à un sprint
        tasks_with_sprint = self.project.tasks.filter(sprint__isnull=False).count()
        self.assertGreater(
            tasks_with_sprint, 0,
            "Aucune tâche n'a été associée à un sprint après approbation.",
        )

    def test_acceptance_criteria_varient_par_type_de_tache(self):
        """Régression : les critères d'acceptation doivent être spécifiques au type.

        Avant le correctif, tous les types avaient les mêmes 3 critères
        génériques. Désormais chaque type possède sa propre liste.
        """
        result = run_scoping({
            "brief": (
                "Refonte portail React, API Django, SSO Keycloak, "
                "recette QA, documentation technique et correctifs critiques."
            ),
            "team": TEAM,
        })

        criteria_by_type: dict[str, list[str]] = {}
        for task in result["tasks"]:
            task_type = task["type"]
            criteria = task["acceptance_criteria"]
            self.assertEqual(
                len(criteria), 3,
                f"La tâche {task['ref']} ({task_type}) doit avoir 3 critères, "
                f"trouvé : {len(criteria)}.",
            )
            # Pour un même type, les critères doivent être identiques
            if task_type in criteria_by_type:
                self.assertEqual(
                    criteria_by_type[task_type], criteria,
                    f"Les critères du type '{task_type}' sont incohérents "
                    f"d'une tâche à l'autre.",
                )
            else:
                criteria_by_type[task_type] = criteria

        # Plusieurs types distincts doivent avoir des critères différents
        unique_criteria = {tuple(v) for v in criteria_by_type.values()}
        self.assertGreater(
            len(unique_criteria), 1,
            f"Tous les types de tâches ont les mêmes critères — variation attendue. "
            f"Types trouvés : {list(criteria_by_type.keys())}",
        )
