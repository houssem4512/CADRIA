"""
Scoping Agent runner — orchestrates RAG → LLM → validation → fallback.

This is the entry point called by orchestration.services.dispatch() when
the agent key is "SCOPING".

Flow:
  1. Extract brief + constraints + team from run.input_payload
  2. RAG: embed brief, retrieve top-3 similar past proposals
  3. Build chat messages (system prompt + brief + RAG context)
  4. Call Groq LLM with JSON mode
  5. Parse + validate with Pydantic ScopingOutput
     - If invalid, retry once with error feedback
     - If still invalid, use deterministic fallback
  6. Create Proposal(status=PENDING) linked to run
  7. Update run.output_payload, status, tokens, latency
  8. Write AuditLog + Notification
  9. Return AgentDispatchResult

If GROQ_API_KEY is not set or the LLM call fails, falls back to the
deterministic engine — the user always gets a plan.
"""
from __future__ import annotations
import json
import logging
import time
from datetime import timedelta
from typing import Any

from django.utils import timezone

from audit.models import AuditLog
from notifications.models import Notification
from orchestration.models import AgentRun, Proposal

from .groq_client import GroqError, chat_completion_json
from .prompts import SCHEMA_HINT, build_messages
from .rag import format_rag_context, retrieve_similar
from .schemas import ScopingOutput
from .fallback import generate_plan as fallback_plan

logger = logging.getLogger(__name__)


def run(run: AgentRun) -> dict[str, Any]:
    """Entry point — called by dispatch() for SCOPING runs."""
    started = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.step = "Analyse du brief"
    run.started_at = started
    run.save(update_fields=["status", "step", "started_at"])

    payload = run.input_payload or {}
    brief = payload.get("brief", "")
    constraints = payload.get("constraints") or {}
    team = payload.get("team") or []
    methodology = payload.get("methodology", "SCRUM")

    correlation_id = f"scp-{run.id:08x}"

    try:
        plan, meta = _generate_plan(brief, constraints, team, methodology)
    except Exception as e:
        logger.exception("Scoping failed for run %s: %s", run.id, e)
        run.status = AgentRun.Status.FAILED
        run.error_message = str(e)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        _audit_fail(run, correlation_id, str(e))
        return {"status": "FAILED", "error": str(e), "output": {}}

    # Validate + normalize via Pydantic
    try:
        validated = ScopingOutput.model_validate(plan)
        proposal_payload = validated.to_proposal_payload()
    except Exception as e:
        logger.warning("Plan validation failed: %s — using raw plan", e)
        proposal_payload = _raw_to_proposal_payload(plan)

    # Persist the Proposal (status PENDING — awaits PM validation)
    proposal = Proposal.objects.create(
        run=run,
        project=run.project,
        title=f"Plan de découpage — {run.project.name}",
        summary=plan.get("summary", brief[:300]),
        status=Proposal.Status.PENDING,
        lots_payload=proposal_payload["lots_payload"],
        tasks_payload=proposal_payload["tasks_payload"],
        sprints_payload=proposal_payload["sprints_payload"],
        risks_payload=proposal_payload["risks_payload"],
        assumptions=proposal_payload["assumptions"],
        total_estimate_hours=proposal_payload["total_estimate_hours"],
        confidence=proposal_payload["confidence"],
    )

    # Update the run
    finished = timezone.now()
    latency_ms = int((finished - started).total_seconds() * 1000)
    run.status = AgentRun.Status.AWAITING_VALIDATION
    run.step = "Plan généré — en attente de validation"
    run.output_payload = {**plan, "proposal_id": proposal.id}
    run.tokens_in = meta.get("tokens_in", 0)
    run.tokens_out = meta.get("tokens_out", 0)
    run.latency_ms = latency_ms
    run.finished_at = finished
    run.save(update_fields=[
        "status", "step", "output_payload", "tokens_in", "tokens_out",
        "latency_ms", "finished_at",
    ])

    # Update agent observability counters
    agent = run.agent
    agent.total_runs = (agent.total_runs or 0) + 1
    agent.successful_runs = (agent.successful_runs or 0) + 1
    agent.last_run_at = finished
    # Rolling average latency
    if agent.avg_latency_ms:
        agent.avg_latency_ms = int((agent.avg_latency_ms + latency_ms) / 2)
    else:
        agent.avg_latency_ms = latency_ms
    agent.save(update_fields=["total_runs", "successful_runs", "last_run_at", "avg_latency_ms"])

    _audit_success(run, correlation_id, proposal, meta)
    _notify_pm(run, proposal)

    return {
        "status": "AWAITING_VALIDATION",
        "output": run.output_payload,
        "proposal_id": proposal.id,
        "tokens_in": meta.get("tokens_in", 0),
        "tokens_out": meta.get("tokens_out", 0),
        "latency_ms": latency_ms,
        "engine": meta.get("engine", "llm"),
    }


def _generate_plan(
    brief: str,
    constraints: dict,
    team: list,
    methodology: str,
) -> tuple[dict, dict]:
    """
    Try LLM first, fall back to deterministic engine if unavailable.

    Returns (plan_dict, meta_dict) where meta contains tokens/latency/engine info.
    """
    # RAG: retrieve similar past projects
    try:
        similar = retrieve_similar(brief, top_k=3)
        rag_context = format_rag_context(similar)
    except Exception as e:
        logger.warning("RAG retrieval failed: %s — continuing without RAG", e)
        rag_context = ""

    # Try LLM
    try:
        messages = build_messages(brief, constraints, team, methodology, rag_context)
        response = chat_completion_json(
            messages=messages,
            schema_hint=SCHEMA_HINT,
            temperature=0.4,
            max_retries=1,
        )
        plan = _parse_llm_response(response["content"])
        plan["_engine"] = "groq-llm"
        if rag_context:
            plan["_rag_used"] = True
        meta = {
            "tokens_in": response["tokens_in"],
            "tokens_out": response["tokens_out"],
            "latency_ms": response["latency_ms"],
            "engine": "groq-llm",
            "model": response["model"],
        }
        return plan, meta
    except GroqError as e:
        logger.warning("Groq LLM failed: %s — using deterministic fallback", e)
    except Exception as e:
        logger.exception("Unexpected LLM error: %s — using deterministic fallback", e)

    # Fallback: deterministic engine
    plan = fallback_plan(brief, constraints, team, methodology)
    meta = {
        "tokens_in": 0,
        "tokens_out": 0,
        "latency_ms": 0,
        "engine": "deterministic-fallback",
        "model": "expert-engine-v1",
    }
    return plan, meta


def _parse_llm_response(content: str) -> dict:
    """Parse the LLM response as JSON. Strips markdown fences if present."""
    import re
    text = content.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```\s*$", "", text, flags=re.IGNORECASE)
    # Extract first {...} block
    first = text.find("{")
    last = text.rfind("}")
    if first != -1 and last != -1:
        text = text[first:last + 1]
    return json.loads(text)


def _raw_to_proposal_payload(plan: dict) -> dict:
    """Convert a raw plan dict to the Proposal payload shape (when Pydantic fails)."""
    return {
        "lots_payload": plan.get("lots", []),
        "tasks_payload": plan.get("tasks", []),
        "sprints_payload": plan.get("sprints", []),
        "risks_payload": plan.get("risks", []),
        "assumptions": plan.get("assumptions", []),
        "total_estimate_hours": float(plan.get("total_estimate_hours", 0) or 0),
        "confidence": float(plan.get("confidence", 0.7) or 0.7),
    }


def _audit_success(run, correlation_id, proposal, meta):
    AuditLog.objects.create(
        actor=run.triggered_by,
        action=AuditLog.Action.AGENT_RUN,
        severity=AuditLog.Severity.NOTICE,
        entity_type="Project",
        entity_id=str(run.project.pk),
        entity_label=run.project.name,
        description=(
            f"Agent 1 (Scoping) — plan généré via {meta.get('engine', 'llm')}. "
            f"Proposal #{proposal.id} en attente de validation. "
            f"{proposal.tasks_count} tâches, {len(proposal.lots_payload)} lots, "
            f"{proposal.total_estimate_hours}h estimées."
        ),
        agent_key="SCOPING",
        run=run,
        correlation_id=correlation_id,
        metadata={
            "engine": meta.get("engine"),
            "model": meta.get("model"),
            "tokens_in": meta.get("tokens_in"),
            "tokens_out": meta.get("tokens_out"),
            "latency_ms": meta.get("latency_ms"),
            "proposal_id": proposal.id,
            "lots": len(proposal.lots_payload),
            "tasks": proposal.tasks_count,
        },
    )


def _audit_fail(run, correlation_id, error_msg):
    AuditLog.objects.create(
        actor=run.triggered_by,
        action=AuditLog.Action.AGENT_RUN,
        severity=AuditLog.Severity.WARNING,
        entity_type="Project",
        entity_id=str(run.project.pk),
        entity_label=run.project.name,
        description=f"Agent 1 (Scoping) — échec: {error_msg[:200]}",
        agent_key="SCOPING",
        run=run,
        correlation_id=correlation_id,
        metadata={"error": error_msg[:500]},
    )


def _notify_pm(run, proposal):
    Notification.objects.create(
        user=run.triggered_by,
        category=Notification.Category.AGENT,
        level=Notification.Level.AGENT,
        title=f"Plan prêt à valider — {run.project.name}",
        message=(
            f"L'Agent 1 a produit un plan de découpage ({proposal.tasks_count} tâches, "
            f"{proposal.total_estimate_hours}h). Validez-le dans l'onglet Validation."
        ),
        link=f"/app/projects/{run.project.pk}/validation",
        entity_type="Proposal",
        entity_id=proposal.pk,
        metadata={"agent": "SCOPING", "proposal_id": proposal.id},
    )
