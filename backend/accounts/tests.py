"""
Tests d'intégration de la plateforme Cadria.

Ces tests exercent réellement les vues, sérialiseurs et modèles — aucune
logique n'est réimplémentée ici.

    python manage.py test --parallel 1
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Skill, Team, UserSkill
from audit.models import AuditLog
from notifications.models import Notification
from orchestration.models import AgentDefinition, AgentRun, AssignmentSuggestion, Proposal
from projects.models import Comment, Integration, Project, RiskAlert, Task, WorkPackage

User = get_user_model()
PASSWORD = "Test@2026"


def make_user(email, **kw):
    """Crée un utilisateur actif via le manager personnalisé.

    Les valeurs par défaut peuvent être écrasées par l'appelant (rôle, statut…).
    """
    defaults = {
        "first_name": "Test", "last_name": "User",
        "role": User.Role.PM, "status": User.Status.ACTIVE, "is_active": True,
    }
    defaults.update(kw)
    return User.objects.create_user(email=email, password=PASSWORD, **defaults)


def client_for(user):
    """Client DRF authentifié par JWT pour un utilisateur donné."""
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def make_project(owner, **kw):
    return Project.objects.create(owner=owner, name=kw.pop("name", "Projet test"),
                                  brief="b" * 60, **kw)


def make_agent(key="SCOPING", **kw):
    defaults = {
        "name": f"Agent {key}", "short_name": key, "icon": "sitemap",
        "color": "#2563EB", "state": AgentDefinition.State.RESERVED,
        "order": 1, "requires_human_validation": True,
        "capabilities": ["cap 1"],
        "input_schema_hint": {"brief": "string"},
        "output_schema_hint": {"tasks": ["..."]},
    }
    defaults.update(kw)
    return AgentDefinition.objects.create(key=key, **defaults)


# ===========================================================================
# Authentification & comptes
# ===========================================================================
class AuthTests(TestCase):
    def test_login_returns_jwt_and_touches_last_seen(self):
        user = make_user("login@test.io")
        self.assertIsNone(user.last_seen_at)
        res = self.client.post("/api/auth/login/", {"email": "login@test.io", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)
        self.assertEqual(res.data["user"]["email"], "login@test.io")
        user.refresh_from_db()
        self.assertIsNotNone(user.last_seen_at)

    def test_login_rejects_wrong_password(self):
        make_user("bad@test.io")
        res = self.client.post("/api/auth/login/", {"email": "bad@test.io", "password": "nope"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_blocks_suspended_account(self):
        make_user("susp@test.io", status=User.Status.SUSPENDED)
        res = self.client.post("/api/auth/login/", {"email": "susp@test.io", "password": PASSWORD}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_creates_un_compte_et_notifie(self):
        res = self.client.post("/api/auth/register/", {
            "email": "new@test.io", "password": "Str0ng!Pass", "password_confirm": "Str0ng!Pass",
            "first_name": "New", "last_name": "User", "role": "PM",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        user = User.objects.get(email="new@test.io")
        self.assertEqual(user.role, User.Role.PM)
        self.assertEqual(user.status, User.Status.ACTIVE)
        self.assertTrue(user.check_password("Str0ng!Pass"))
        self.assertTrue(Notification.objects.filter(user=user).exists())
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.SIGNUP, actor=user).exists())

    def test_register_refuse_role_admin(self):
        res = self.client.post("/api/auth/register/", {
            "email": "hack@test.io", "password": "Str0ng!Pass", "password_confirm": "Str0ng!Pass",
            "first_name": "H", "last_name": "X", "role": "ADMIN",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="hack@test.io").exists())

    def test_register_refuse_email_duplique(self):
        make_user("dupe@test.io")
        res = self.client.post("/api/auth/register/", {
            "email": "dupe@test.io", "password": "Str0ng!Pass", "password_confirm": "Str0ng!Pass",
            "first_name": "A", "last_name": "B",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_refuse_mots_de_passe_divergents(self):
        res = self.client.post("/api/auth/register/", {
            "email": "mism@test.io", "password": "Str0ng!Pass", "password_confirm": "Other!Pass",
            "first_name": "A", "last_name": "B",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_requiert_authentification(self):
        self.assertEqual(self.client.get("/api/me/").status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_patch_met_a_jour_le_profil(self):
        user = make_user("me@test.io")
        res = client_for(user).patch("/api/me/", {"job_title": "Lead PM"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertEqual(user.job_title, "Lead PM")

    def test_password_change_verifie_ancien_mot_de_passe(self):
        user = make_user("pwd@test.io")
        c = client_for(user)
        bad = c.post("/api/auth/password/change/", {"old_password": "wrong", "new_password": "N3w!Passw"}, format="json")
        self.assertEqual(bad.status_code, status.HTTP_400_BAD_REQUEST)
        good = c.post("/api/auth/password/change/", {"old_password": PASSWORD, "new_password": "N3w!Passw"}, format="json")
        self.assertEqual(good.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("N3w!Passw"))

    def test_reset_password_par_code(self):
        make_user("reset@test.io")
        res = self.client.post("/api/auth/password/reset/", {"email": "reset@test.io"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        code = res.data["demo_code"]
        self.assertEqual(len(code), 6)
        conf = self.client.post("/api/auth/password/reset/confirm/", {
            "email": "reset@test.io", "code": code, "new_password": "Fresh!Pass1",
        }, format="json")
        self.assertEqual(conf.status_code, status.HTTP_200_OK, conf.data)
        self.assertTrue(User.objects.get(email="reset@test.io").check_password("Fresh!Pass1"))

    def test_reset_rejette_code_invalide(self):
        make_user("badcode@test.io")
        self.client.post("/api/auth/password/reset/", {"email": "badcode@test.io"}, format="json")
        res = self.client.post("/api/auth/password/reset/confirm/", {
            "email": "badcode@test.io", "code": "000000", "new_password": "Fresh!Pass1",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# Autorisations & administration des comptes
# ===========================================================================
class PermissionsTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin@test.io", role=User.Role.ADMIN)
        self.pm = make_user("pm2@test.io", role=User.Role.PM)
        self.member = make_user("mem@test.io", role=User.Role.MEMBER)

    def test_crud_comptes_reserve_aux_admins(self):
        self.assertEqual(client_for(self.admin).get("/api/users/").status_code, status.HTTP_200_OK)
        for u in (self.pm, self.member):
            self.assertEqual(client_for(u).get("/api/users/").status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_cree_un_compte(self):
        res = client_for(self.admin).post("/api/users/", {
            "email": "created@test.io", "first_name": "C", "last_name": "R",
            "role": "MEMBER", "password": "Pwd@2026",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        u = User.objects.get(email="created@test.io")
        self.assertTrue(u.check_password("Pwd@2026"))
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.CREATE, entity_type="User").exists())

    def test_admin_suspend_et_reactive_un_compte(self):
        res = client_for(self.admin).post(f"/api/users/{self.member.pk}/toggle_active/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data["is_active"])
        self.assertEqual(res.data["status"], User.Status.SUSPENDED)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)
        res2 = client_for(self.admin).post(f"/api/users/{self.member.pk}/toggle_active/")
        self.assertTrue(res2.data["is_active"])

    def test_actions_groupees(self):
        a = make_user("g1@test.io", role=User.Role.MEMBER)
        b = make_user("g2@test.io", role=User.Role.MEMBER)
        res = client_for(self.admin).post("/api/users/bulk_action/", {
            "ids": [a.pk, b.pk], "action": "suspend",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["updated"], 2)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertFalse(a.is_active and b.is_active)

    def test_reinitialisation_mot_de_passe_par_admin(self):
        res = client_for(self.admin).post(f"/api/users/{self.member.pk}/reset_password/", {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertTrue(self.member.check_password(res.data["password"]))

    def test_analytics_admin_reserve_aux_admins(self):
        self.assertEqual(client_for(self.admin).get("/api/analytics/admin/").status_code, status.HTTP_200_OK)
        self.assertEqual(client_for(self.pm).get("/api/analytics/admin/").status_code, status.HTTP_403_FORBIDDEN)

    def test_broadcast_reserve_aux_admins(self):
        payload = {"title": "Annonce", "message": "msg", "target_role": "ALL"}
        self.assertEqual(client_for(self.admin).post("/api/notifications/broadcast/", payload, format="json").status_code,
                         status.HTTP_201_CREATED)
        self.assertEqual(client_for(self.pm).post("/api/notifications/broadcast/", payload, format="json").status_code,
                         status.HTTP_403_FORBIDDEN)


class RoleSeparationTests(TestCase):
    """Séparation des interfaces : création et pilotage réservés aux PM/ADMIN."""

    def setUp(self):
        self.admin = make_user("rs-admin@test.io", role=User.Role.ADMIN)
        self.pm = make_user("rs-pm@test.io", role=User.Role.PM)
        self.member = make_user("rs-mem@test.io", role=User.Role.MEMBER)

    def test_member_ne_peut_pas_creer_de_projet(self):
        res = client_for(self.member).post("/api/projects/", {
            "name": "Interdit", "brief": "b" * 60,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.filter(name="Interdit").exists())

    def test_admin_peut_creer_un_projet(self):
        res = client_for(self.admin).post("/api/projects/", {
            "name": "Projet admin", "brief": "b" * 60,
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_pm_cree_un_projet_et_choisit_son_equipe(self):
        other = make_user("rs-mem2@test.io", role=User.Role.MEMBER)
        res = client_for(self.pm).post("/api/projects/", {
            "name": "Projet équipe", "brief": "b" * 60,
            "member_ids": [self.member.pk, other.pk],
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        project = Project.objects.get(pk=res.data["id"])
        self.assertEqual(project.owner, self.pm)
        self.assertEqual(set(project.members.values_list("pk", flat=True)),
                         {self.pm.pk, self.member.pk, other.pk})

    def test_lancement_agent_reserve_au_proprietaire_ou_admin(self):
        agent = make_agent()
        project = make_project(owner=self.pm, name="Pilotage")
        project.members.add(self.member)
        payload = {"project": project.pk, "agent": agent.key, "input": {}}
        self.assertEqual(
            client_for(self.member).post("/api/agents/runs/start/", payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            client_for(self.pm).post("/api/agents/runs/start/", payload, format="json").status_code,
            status.HTTP_202_ACCEPTED)
        self.assertEqual(
            client_for(self.admin).post("/api/agents/runs/start/", payload, format="json").status_code,
            status.HTTP_202_ACCEPTED)

    def test_validation_proposition_reservee_au_proprietaire_ou_admin(self):
        project = make_project(owner=self.pm, name="Validation")
        proposal = Proposal.objects.create(project=project, title="Plan",
                                           status=Proposal.Status.PENDING)
        payload = {"decision": "APPROVE", "create_tasks": True}
        self.assertEqual(
            client_for(self.member).post(
                f"/api/proposals/{proposal.pk}/validate/", payload, format="json").status_code,
            status.HTTP_403_FORBIDDEN)
        res = client_for(self.pm).post(
            f"/api/proposals/{proposal.pk}/validate/", payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)


# ===========================================================================
# Projets & tâches
# ===========================================================================
class ProjectTests(TestCase):
    def setUp(self):
        self.pm = make_user("ppm@test.io", role=User.Role.PM)
        self.other = make_user("other@test.io", role=User.Role.PM)
        self.project = make_project(self.pm, name="Mon projet")

    def test_reference_et_slug_attribues_automatiquement(self):
        self.assertTrue(self.project.reference.startswith("PRJ-"))
        self.assertTrue(self.project.slug)

    def test_creation_renvoie_la_representation_detaillee(self):
        res = client_for(self.pm).post("/api/projects/", {
            "name": "Nouveau", "summary": "s", "brief": "b" * 60, "methodology": "SCRUM",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertIn("reference", res.data)
        self.assertIn("health_indicators", res.data)
        self.assertIn("work_packages", res.data)

    def test_un_utilisateur_etranger_ne_voit_pas_le_projet(self):
        self.assertEqual(client_for(self.other).get("/api/projects/").data["count"], 0)
        self.assertEqual(client_for(self.other).get(f"/api/projects/{self.project.pk}/").status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_recompute_agrege_progression_et_risque(self):
        for i in range(4):
            Task.objects.create(project=self.project, title=f"T{i}",
                                status=Task.Status.DONE if i < 2 else Task.Status.TODO,
                                estimate_hours=10, spent_hours=5)
        RiskAlert.objects.create(project=self.project, title="Alerte", severity=RiskAlert.Severity.CRITICAL,
                                 score=80, category=RiskAlert.Category.DELAY)
        res = client_for(self.pm).post(f"/api/projects/{self.project.pk}/recompute/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.project.refresh_from_db()
        self.assertEqual(self.project.progress, 50)
        self.assertEqual(float(self.project.estimated_effort_hours), 40.0)
        self.assertGreaterEqual(float(self.project.risk_score), 20)

    def test_board_groupe_les_taches_par_statut(self):
        Task.objects.create(project=self.project, title="A", status=Task.Status.TODO)
        Task.objects.create(project=self.project, title="B", status=Task.Status.DONE)
        res = client_for(self.pm).get(f"/api/projects/{self.project.pk}/board/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        counts = {c["key"]: len(c["tasks"]) for c in res.data["columns"]}
        self.assertEqual(counts["TODO"], 1)
        self.assertEqual(counts["DONE"], 1)

    def test_move_change_le_statut_d_une_tache(self):
        t = Task.objects.create(project=self.project, title="M", status=Task.Status.TODO)
        res = client_for(self.pm).post(f"/api/tasks/{t.pk}/move/", {"status": "IN_PROGRESS"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        t.refresh_from_db()
        self.assertEqual(t.status, Task.Status.IN_PROGRESS)
        self.assertFalse(t.blocked)

    def test_move_vers_blocked_positionne_le_flag(self):
        t = Task.objects.create(project=self.project, title="B", status=Task.Status.TODO)
        client_for(self.pm).post(f"/api/tasks/{t.pk}/move/", {"status": "BLOCKED"}, format="json")
        t.refresh_from_db()
        self.assertTrue(t.blocked)

    def test_move_rejette_un_statut_invalide(self):
        t = Task.objects.create(project=self.project, title="X")
        res = client_for(self.pm).post(f"/api/tasks/{t.pk}/move/", {"status": "NOPE"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_task_terminee_horodate_completed_at(self):
        t = Task.objects.create(project=self.project, title="D", status=Task.Status.DONE)
        self.assertIsNotNone(t.completed_at)
        t.status = Task.Status.TODO
        t.save()
        self.assertIsNone(t.completed_at)

    def test_effort_variance_et_cout(self):
        m = make_user("dev@test.io", role=User.Role.MEMBER, hourly_cost=Decimal("100.00"))
        t = Task.objects.create(project=self.project, title="V", estimate_hours=10, spent_hours=15, assignee=m)
        self.assertEqual(t.effort_variance, 50.0)
        self.assertEqual(t.cost, 1500.0)

    def test_workload_renvoie_charge_par_membre(self):
        m = make_user("wl@test.io", role=User.Role.MEMBER, weekly_capacity_hours=Decimal("40.0"))
        self.project.members.add(m)
        Task.objects.create(project=self.project, title="W", estimate_hours=20, assignee=m)
        res = client_for(self.pm).get(f"/api/projects/{self.project.pk}/workload/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        row = [r for r in res.data if r["id"] == m.pk][0]
        self.assertEqual(float(row["estimated_hours"]), 20.0)
        self.assertEqual(row["utilisation_pct"], 50.0)

    def test_commentaire_detecte_un_signal_faible(self):
        res = client_for(self.pm).post("/api/comments/", {
            "project": self.project.pk, "body": "Je suis bloqué en attente de validation",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        c = Comment.objects.get(project=self.project)
        self.assertTrue(c.weak_signal)
        self.assertEqual(c.sentiment, "NEGATIVE")

    def test_commentaire_neutre(self):
        client_for(self.pm).post("/api/comments/", {"project": self.project.pk, "body": "Réunion validée"}, format="json")
        c = Comment.objects.filter(project=self.project).first()
        self.assertFalse(c.weak_signal)


# ===========================================================================
# Agents — emplacements réservés & validation humaine
# ===========================================================================
class AgentTests(TestCase):
    def setUp(self):
        self.pm = make_user("apm@test.io", role=User.Role.PM)
        self.project = make_project(self.pm, name="Projet agent")
        self.agent = make_agent("SCOPING")

    def test_lancement_cree_une_execution_reservee(self):
        res = client_for(self.pm).post("/api/agents/runs/start/", {
            "project": self.project.pk, "agent": "SCOPING", "input": {"brief": "x"},
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED, res.data)
        self.assertTrue(res.data["reserved"])
        run = AgentRun.objects.get(pk=res.data["run"]["id"])
        self.assertEqual(run.status, AgentRun.Status.SKIPPED)
        self.assertTrue(run.output_payload["_reserved"])
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.total_runs, 1)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.AGENT_RUN, agent_key="SCOPING").exists())
        self.assertTrue(Notification.objects.filter(category=Notification.Category.AGENT).exists())

    def test_lancement_agent_inconnu(self):
        res = client_for(self.pm).post("/api/agents/runs/start/", {
            "project": self.project.pk, "agent": "NOPE",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_lancement_projet_inexistant(self):
        res = client_for(self.pm).post("/api/agents/runs/start/", {"project": 99999, "agent": "SCOPING"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_monitor_agrege_les_executions(self):
        for i in range(3):
            AgentRun.objects.create(project=self.project, agent=self.agent, status=AgentRun.Status.SKIPPED)
        res = client_for(self.pm).get("/api/agents/monitor/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["totals"]["runs"], 3)
        self.assertEqual(res.data["totals"]["skipped"], 3)
        self.assertFalse(res.data["enabled"])
        row = res.data["per_agent"][0]
        self.assertEqual(row["total"], 3)

    def test_validation_approuvee_materialise_les_taches(self):
        lot = WorkPackage.objects.create(project=self.project, name="Lot A", order=0)
        proposal = Proposal.objects.create(
            project=self.project, title="Plan", status=Proposal.Status.PENDING,
            lots_payload=[{"name": "Lot A", "description": "d", "estimate_hours": 40,
                           "confidence": 0.8, "color": "#2563EB", "order": 0}],
            tasks_payload=[
                {"ref": "T-001", "lot": "Lot A", "title": "Tâche un", "description": "x",
                 "type": "FEATURE", "priority": "HIGH", "estimate_hours": 16, "story_points": 2,
                 "skills": ["Python"], "acceptance_criteria": ["ok"], "risk_score": 20},
                {"ref": "T-002", "lot": "Lot A", "title": "Tâche deux", "description": "y",
                 "type": "BUG", "priority": "MEDIUM", "estimate_hours": 8, "story_points": 1,
                 "skills": ["Django"], "acceptance_criteria": ["ok"], "risk_score": 10},
            ],
            total_estimate_hours=Decimal("24"),
        )
        member = make_user("assignee@test.io", role=User.Role.MEMBER)
        sug = AssignmentSuggestion.objects.create(
            proposal=proposal, task_ref="T-001", task_title="Tâche un", candidate=member,
            match_score=Decimal("0.91"), accepted=None,
        )
        res = client_for(self.pm).post(f"/api/proposals/{proposal.pk}/validate/", {
            "decision": "APPROVE", "create_tasks": True,
            "assignments": {str(sug.pk): True},
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertEqual(res.data["created_tasks"], 2)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, Proposal.Status.APPROVED)
        self.assertEqual(proposal.validated_by, self.pm)
        self.assertIsNotNone(proposal.validated_at)
        self.assertEqual(self.project.tasks.count(), 2)
        t1 = self.project.tasks.get(title="Tâche un")
        self.assertTrue(t1.created_by_agent)
        self.assertEqual(t1.assignee, member)
        self.assertEqual(t1.work_package.name, "Lot A")
        sug.refresh_from_db()
        self.assertTrue(sug.accepted)

    def test_validation_rejetee_ne_cree_rien(self):
        proposal = Proposal.objects.create(
            project=self.project, title="Plan rejeté", status=Proposal.Status.PENDING,
            tasks_payload=[{"ref": "T-1", "title": "T", "estimate_hours": 5}],
        )
        res = client_for(self.pm).post(f"/api/proposals/{proposal.pk}/validate/", {
            "decision": "REJECT", "reason": "Périmètre trop large",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, Proposal.Status.REJECTED)
        self.assertEqual(proposal.rejection_reason, "Périmètre trop large")
        self.assertEqual(self.project.tasks.count(), 0)

    def test_validation_rejette_une_decision_invalide(self):
        proposal = Proposal.objects.create(project=self.project, title="P", status=Proposal.Status.PENDING)
        res = client_for(self.pm).post(f"/api/proposals/{proposal.pk}/validate/", {"decision": "MAYBE"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_decision_sur_une_suggestion(self):
        proposal = Proposal.objects.create(project=self.project, title="P", status=Proposal.Status.PENDING)
        m = make_user("cand@test.io", role=User.Role.MEMBER)
        sug = AssignmentSuggestion.objects.create(proposal=proposal, task_ref="T-1", candidate=m,
                                                  match_score=Decimal("0.7"))
        res = client_for(self.pm).post(f"/api/assignments/{sug.pk}/decide/", {"accepted": True}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        sug.refresh_from_db()
        self.assertTrue(sug.accepted)


# ===========================================================================
# Notifications
# ===========================================================================
class NotificationTests(TestCase):
    def setUp(self):
        self.user = make_user("notif@test.io", role=User.Role.PM)
        self.admin = make_user("nadmin@test.io", role=User.Role.ADMIN)
        self.c = client_for(self.user)

    def test_summary_compte_les_non_lues(self):
        Notification.objects.create(user=self.user, title="A")
        Notification.objects.create(user=self.user, title="B", read=True, read_at=timezone.now())
        res = self.c.get("/api/notifications/summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["unread"], 1)
        self.assertEqual(res.data["total"], 2)

    def test_mark_read_marque_la_notification(self):
        n = Notification.objects.create(user=self.user, title="A")
        res = self.c.post(f"/api/notifications/{n.pk}/mark_read/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.read)
        self.assertIsNotNone(n.read_at)

    def test_mark_all_read(self):
        for i in range(3):
            Notification.objects.create(user=self.user, title=f"N{i}")
        res = self.c.post("/api/notifications/mark_all_read/")
        self.assertEqual(res.data["marked"], 3)
        self.assertEqual(Notification.objects.filter(user=self.user, read=False).count(), 0)

    def test_toggle_star_et_archive(self):
        n = Notification.objects.create(user=self.user, title="A")
        r1 = self.c.post(f"/api/notifications/{n.pk}/toggle_star/")
        self.assertTrue(r1.data["starred"])
        r2 = self.c.post(f"/api/notifications/{n.pk}/archive/")
        self.assertTrue(r2.data["archived"])
        n.refresh_from_db()
        self.assertTrue(n.starred and n.archived)

    def test_diffusion_visible_par_tous_les_roles(self):
        Notification.objects.create(user=None, is_broadcast=True, target_role="ALL", title="Diffusion")
        res = self.c.get("/api/notifications/")
        self.assertEqual(res.data["count"], 1)
        self.assertTrue(res.data["results"][0]["is_broadcast"])

    def test_diffusion_ciblee_par_role(self):
        Notification.objects.create(user=None, is_broadcast=True, target_role="ADMIN", title="Admin only")
        self.assertEqual(self.c.get("/api/notifications/").data["count"], 0)
        self.assertEqual(client_for(self.admin).get("/api/notifications/").data["count"], 1)

    def test_lecture_individuelle_d_une_diffusion(self):
        n = Notification.objects.create(user=None, is_broadcast=True, target_role="ALL", title="D")
        self.c.post(f"/api/notifications/{n.pk}/mark_read/")
        res = self.c.get("/api/notifications/")
        self.assertTrue(res.data["results"][0]["is_read"])
        # un autre utilisateur ne l'a pas lue
        other = make_user("other2@test.io", role=User.Role.PM)
        res2 = client_for(other).get("/api/notifications/")
        self.assertFalse(res2.data["results"][0]["is_read"])

    def test_preferences_lecture_et_ecriture(self):
        res = self.c.get("/api/notifications/preferences/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        patch = self.c.patch("/api/notifications/preferences/", {"slack": True, "digest_frequency": "WEEKLY"}, format="json")
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        self.assertTrue(patch.data["slack"])
        self.assertEqual(patch.data["digest_frequency"], "WEEKLY")


# ===========================================================================
# Équipes, compétences & annuaire
# ===========================================================================
class TeamTests(TestCase):
    def setUp(self):
        self.pm = make_user("tpm@test.io", role=User.Role.PM)
        self.member = make_user("tmem@test.io", role=User.Role.MEMBER)

    def test_creation_d_equipe_ajoute_le_proprietaire(self):
        res = client_for(self.pm).post("/api/teams/", {
            "name": "Squad A", "description": "d", "color": "#2563EB",
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        team = Team.objects.get(name="Squad A")
        self.assertEqual(team.owner, self.pm)
        self.assertIn(self.pm, team.members.all())

    def test_annuaire_des_membres(self):
        res = client_for(self.pm).get("/api/members/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [m["email"] for m in res.data["results"]]
        self.assertIn("tpm@test.io", emails)
        self.assertIn("tmem@test.io", emails)

    def test_competences_personnelles(self):
        skill = Skill.objects.create(name="Python", category="TECH")
        c = client_for(self.member)
        res = c.put("/api/me/skills/", [{"skill": skill.pk, "level": 4}], format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(UserSkill.objects.filter(user=self.member).count(), 1)
        got = c.get("/api/me/skills/")
        self.assertEqual(got.data[0]["name"], "Python")
        self.assertEqual(got.data[0]["level"], 4)


# ===========================================================================
# Journal d'audit
# ===========================================================================
class AuditTests(TestCase):
    def setUp(self):
        self.pm = make_user("aud@test.io", role=User.Role.PM)
        self.admin = make_user("audadmin@test.io", role=User.Role.ADMIN)

    def test_non_admin_ne_voit_que_ses_actions(self):
        AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.CREATE, description="à moi")
        AuditLog.objects.create(actor=self.admin, action=AuditLog.Action.CREATE, description="à l'admin")
        res = client_for(self.pm).get("/api/audit/")
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["description"], "à moi")

    def test_admin_voit_tout(self):
        AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.CREATE, description="a")
        AuditLog.objects.create(actor=self.admin, action=AuditLog.Action.DELETE, description="b")
        self.assertEqual(client_for(self.admin).get("/api/audit/").data["count"], 2)

    def test_filtres_par_action_et_agent(self):
        AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.AGENT_RUN, agent_key="RISK")
        AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.CREATE)
        self.assertEqual(client_for(self.pm).get("/api/audit/?action=AGENT_RUN").data["count"], 1)
        self.assertEqual(client_for(self.pm).get("/api/audit/?agent=RISK").data["count"], 1)

    def test_summary_agrege(self):
        for i in range(3):
            AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.CREATE)
        AuditLog.objects.create(actor=self.pm, action=AuditLog.Action.AGENT_RUN, agent_key="OPS")
        res = client_for(self.pm).get("/api/audit/summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["total"], 4)
        agents = {a["key"]: a["count"] for a in res.data["by_agent"]}
        self.assertEqual(agents["OPS"], 1)


# ===========================================================================
# Analytics
# ===========================================================================
class AnalyticsTests(TestCase):
    def setUp(self):
        self.pm = make_user("anpm@test.io", role=User.Role.PM)
        self.admin = make_user("anadmin@test.io", role=User.Role.ADMIN)
        self.project = make_project(self.pm)
        for i in range(5):
            Task.objects.create(project=self.project, title=f"T{i}",
                                status=Task.Status.DONE if i < 3 else Task.Status.TODO,
                                estimate_hours=Decimal("10"), spent_hours=Decimal("5"))

    def test_dashboard_client_agrege_les_kpi(self):
        res = client_for(self.pm).get("/api/analytics/dashboard/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        k = res.data["kpis"]
        self.assertEqual(k["tasks_total"], 5)
        self.assertEqual(k["tasks_done"], 3)
        self.assertEqual(k["completion_rate"], 60.0)
        self.assertEqual(len(res.data["status_distribution"]), 5)

    def test_dashboard_admin_agrege(self):
        res = client_for(self.admin).get("/api/analytics/admin/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        k = res.data["kpis"]
        self.assertEqual(k["projects"], 1)
        self.assertEqual(k["tasks"], 5)
        self.assertIn("platform_health", k)
        self.assertEqual(len(res.data["growth"]), 6)

    def test_insights_qualite(self):
        res = client_for(self.admin).get("/api/analytics/insights/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("generation_quality", res.data)
        self.assertIn("assignment_quality", res.data)
        self.assertIn("risk_quality", res.data)
