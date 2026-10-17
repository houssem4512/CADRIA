"""Orchestrateur LangGraph de l'Agent 2 : validation -> epics -> sprints -> membres -> tâches -> finalisation."""
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from orchestration.models import Proposal


class OpsState(TypedDict):
    failed: str                                   # message d'échec bloquant ("" si tout va bien)
    created: Annotated[list, operator.add]        # tickets/cartes créés
    assignments: Annotated[list, operator.add]    # assignations effectuées
    errors: Annotated[list, operator.add]         # erreurs non bloquantes
    trace: Annotated[list, operator.add]          # appels d'outils, dans l'ordre


def initial_state():
    return {"failed": "", "created": [], "assignments": [], "errors": [], "trace": []}


def build_graph(box, proposal, project):
    def validate(state):
        """Porte de validation humaine : aucune écriture réelle sans plan approuvé."""
        approved = (Proposal.Status.APPROVED, Proposal.Status.APPLIED)
        if not box.dry_run and proposal.status not in approved:
            return {"failed": "Validation humaine requise : plan non approuvé.", "trace": []}
        if not box.dry_run and not project.external_key:
            return {"failed": "project.external_key (clé du projet / id du board) est vide.", "trace": []}
        return {"failed": "", "trace": []}

    def epics(state):
        errors = []
        for wp in project.work_packages.all():
            res, err = box.create_epic(wp)
            if err:
                errors.append(err)
            elif res is None:
                break                      # ce fournisseur n'a pas d'epics (Trello)
        return {"errors": errors, "trace": box.drain_trace()}

    def sprints(state):
        errors = []
        for sprint in project.sprints.all():
            _, err = box.create_sprint(sprint)
            if err:
                errors.append(err)
        return {"errors": errors, "trace": box.drain_trace()}

    def members(state):
        err = box.load_members(project.members.all())
        return {"errors": [err] if err else [], "trace": box.drain_trace()}

    def tasks(state):
        created, assignments, errors = [], [], []
        for task in project.tasks.filter(external_id="").select_related("assignee"):
            res, err = box.create_issue(task)
            if err:
                errors.append(err)
                continue
            created.append({
                "entity": "issue", "task_id": task.pk,
                "external_id": res["id"], "external_url": res.get("url", ""), "dry_run": box.dry_run,
            })
            if task.assignee is None:
                continue
            assigned, aerr = box.assign_issue(task, res["id"])
            if aerr:
                errors.append(aerr)
            else:
                assignments.append(assigned)
        return {"created": created, "assignments": assignments, "errors": errors,
                "trace": box.drain_trace()}

    def finalize(state):
        if not box.dry_run and not state["errors"]:
            proposal.status = Proposal.Status.APPLIED
            proposal.save(update_fields=["status"])
        return {"trace": []}

    g = StateGraph(OpsState)
    for name, fn in [("validate", validate), ("epics", epics), ("sprints", sprints),
                     ("members", members), ("tasks", tasks), ("finalize", finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "validate")
    g.add_conditional_edges("validate", lambda s: "stop" if s["failed"] else "go",
                            {"go": "epics", "stop": END})
    g.add_edge("epics", "sprints")
    g.add_edge("sprints", "members")
    g.add_edge("members", "tasks")
    g.add_edge("tasks", "finalize")
    g.add_edge("finalize", END)
    return g.compile()