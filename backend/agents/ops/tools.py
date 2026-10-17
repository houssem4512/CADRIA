"""Outils (tool-calling) de l'Agent 2 : chaque outil a un nom, un schéma d'arguments et laisse une trace."""
import requests

from audit.models import AuditLog

# Schéma de chaque outil : ce que l'orchestrateur peut appeler, avec quels arguments.
TOOL_SCHEMAS = {
    "create_epic": {"description": "Crée un epic pour un lot de travail (Jira)", "args": ["work_package_id"]},
    "create_sprint": {"description": "Crée un sprint (liste Trello / sprint Jira)", "args": ["sprint_id"]},
    "list_members": {"description": "Liste les membres assignables du board/projet", "args": []},
    "create_issue": {"description": "Crée un ticket/carte dans son sprint", "args": ["task_id"]},
    "assign_issue": {"description": "Assigne un ticket/carte à un membre", "args": ["task_id", "member"]},
}


def _norm(text):
    return " ".join((text or "").lower().split())


class OpsToolbox:
    """Regroupe les outils de l'agent et l'état d'exécution partagé (client, identifiants externes)."""

    def __init__(self, run, client, provider, corr, dry_run):
        self.run = run
        self.client = client
        self.provider = provider
        self.label = provider.title()          # "Trello" / "Jira"
        self.corr = corr
        self.dry_run = dry_run
        self.epic_ids, self.sprint_ids, self.member_ids = {}, {}, {}
        self._trace, self._seq = [], 0

    # --- traçabilité ---------------------------------------------------------
    def _record(self, tool, args, ok, detail=""):
        self._seq += 1
        self._trace.append({
            "seq": self._seq, "agent": "OPS", "tool": tool,
            "args": args, "ok": ok, "detail": detail, "dry_run": self.dry_run,
        })

    def drain_trace(self):
        out, self._trace = self._trace, []
        return out

    def _audit(self, entity, label, description, metadata):
        AuditLog.objects.create(
            actor=self.run.triggered_by,
            action=AuditLog.Action.AGENT_WRITE,
            severity=AuditLog.Severity.INFO,
            entity_type=type(entity).__name__,
            entity_id=str(entity.pk),
            entity_label=label,
            description=description,
            agent_key="OPS",
            run=self.run,
            correlation_id=self.corr,
            metadata=metadata,
        )

    def _call(self, tool, args, fn):
        """Appelle un outil : vérifie ses arguments, exécute, trace. Renvoie (résultat, erreur)."""
        missing = [k for k in TOOL_SCHEMAS[tool]["args"] if k not in args]
        if missing:
            raise ValueError(f"Outil {tool} : argument(s) manquant(s) {missing}")
        try:
            result = fn()
        except (RuntimeError, requests.RequestException) as exc:
            self._record(tool, args, False, str(exc))
            return None, str(exc)
        if result is None:
            detail = "non supporté par ce fournisseur"
        elif isinstance(result, dict):
            detail = str(result.get("id", ""))
        else:
            detail = f"{len(result)} élément(s)"
        self._record(tool, args, True, detail)
        return result, ""

    # --- outils --------------------------------------------------------------
    def create_epic(self, wp):
        """(dict, "") si créé ou déjà existant ; (None, "") si le fournisseur n'a pas d'epics."""
        args = {"work_package_id": wp.pk}
        if wp.external_id:
            self.epic_ids[wp.pk] = wp.external_id
            self._record("create_epic", args, True, "déjà créé (idempotence)")
            return {"id": wp.external_id}, ""
        res, err = self._call("create_epic", args, lambda: self.client.create_epic(wp.name, wp.description))
        if err:
            return None, f"Epic « {wp.name} » : {err}"
        if res is None:
            return None, ""
        self.epic_ids[wp.pk] = res["id"]
        if not self.dry_run:
            wp.external_id = res["id"]
            wp.save(update_fields=["external_id"])
            self._audit(wp, wp.name, f"Epic {self.label} créé : {wp.name}",
                        {"provider": self.provider, "external_id": res["id"]})
        return res, ""

    def create_sprint(self, sprint):
        args = {"sprint_id": sprint.pk}
        if sprint.external_id:
            self.sprint_ids[sprint.pk] = sprint.external_id
            self._record("create_sprint", args, True, "déjà créé (idempotence)")
            return {"id": sprint.external_id}, ""
        res, err = self._call("create_sprint", args, lambda: self.client.create_sprint(sprint.name))
        if err:
            return None, f"Sprint « {sprint.name} » : {err}"
        self.sprint_ids[sprint.pk] = res["id"]
        if not self.dry_run:
            sprint.external_id = res["id"]
            sprint.save(update_fields=["external_id"])
            self._audit(sprint, sprint.name, f"Sprint {self.label} créé : {sprint.name}",
                        {"provider": self.provider, "external_id": res["id"]})
        return res, ""

    def load_members(self, users):
        """Associe les membres Cadria aux comptes du fournisseur (par nom complet). Renvoie une erreur ou ""."""
        if self.dry_run:
            self._record("list_members", {}, True, "ignoré en simulation")
            return ""
        res, err = self._call("list_members", {}, self.client.list_members)
        if err:
            return f"Membres {self.label} : {err}"
        by_name = {_norm(m.get("fullName", "")): m["id"] for m in res}
        self.member_ids = {u.pk: by_name.get(_norm(u.full_name)) for u in users}
        return ""

    def create_issue(self, task):
        list_id = self.sprint_ids.get(task.sprint_id)
        if not list_id:
            return None, f"Tâche « {task.title} » : aucun sprint, ignorée."
        payload = {
            "title": task.title,
            "description": task.description,
            "type": task.task_type,
            "priority": task.priority,
            "story_points": task.story_points,
            "skills": task.required_skills,
            "epic_id": self.epic_ids.get(task.work_package_id),
        }
        res, err = self._call("create_issue", {"task_id": task.pk},
                              lambda: self.client.create_task(list_id, payload))
        if err:
            return None, f"Tâche « {task.title} » : {err}"
        if not self.dry_run:
            task.external_id = res["id"]
            task.external_url = res.get("url", "")
            task.save(update_fields=["external_id", "external_url"])
            self._audit(task, task.title, f"Ticket {self.label} créé : {task.title}",
                        {"provider": self.provider, "external_id": res["id"]})
        return res, ""

    def assign_issue(self, task, card_id):
        who = task.assignee
        args = {"task_id": task.pk, "member": who.full_name}
        if self.dry_run:
            self._record("assign_issue", args, True, "simulé")
            return {"task_id": task.pk, "member": who.full_name, "dry_run": True}, ""
        member_id = self.member_ids.get(who.pk)
        if not member_id:
            self._record("assign_issue", args, False, "membre introuvable")
            return None, f"Tâche « {task.title} » : {who.full_name} est introuvable sur {self.label}."
        res, err = self._call("assign_issue", args, lambda: self.client.assign(card_id, member_id))
        if err:
            return None, f"Assignation « {task.title} » : {err}"
        self._audit(task, task.title, f"{who.full_name} assigné(e) à « {task.title} »",
                    {"provider": self.provider, "member_external_id": member_id})
        return {"task_id": task.pk, "member": who.full_name,
                "member_external_id": member_id, "dry_run": False}, ""