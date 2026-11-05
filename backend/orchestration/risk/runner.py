"""
Agent 3 — Risk runner.

Flow:
  1. Load project + tasks + comments
  2. Run NLP on comments (detect weak signals, update Comment records)
  3. Extract per-task features
  4. Score each task with XGBoost
  5. Explain top-3 factors via SHAP (or rule-based)
  6. Create RiskAlert records for high-risk tasks (score > 0.5)
  7. Compute project-level risk score
  8. Update project.risk_score + health
  9. Write AuditLog + Notification

Triggered:
  - On demand (POST /api/agents/runs/start/ with agent=RISK)
  - Weekly via Celery beat (see orchestration/tasks.py)
"""
from __future__ import annotations
import logging
from typing import Any

from django.utils import timezone

from audit.models import AuditLog
from notifications.models import Notification
from orchestration.models import AgentRun
from projects.models import Comment, RiskAlert

from .features import (
    build_feature_vector, extract_project_features, extract_comment_signals,
    FEATURE_NAMES,
)
from .nlp import analyze_comments
from .scorer import predict, explain, ensure_model_ready

logger = logging.getLogger(__name__)

# Threshold for creating a RiskAlert
ALERT_THRESHOLD = 0.5
HIGH_ALERT_THRESHOLD = 0.75


def run(run: AgentRun) -> dict[str, Any]:
    started = timezone.now()
    run.status = AgentRun.Status.RUNNING
    run.step = "Analyse des risques"
    run.started_at = started
    run.save(update_fields=["status", "step", "started_at"])

    correlation_id = f"rsk-{run.id:08x}"
    project = run.project
    model_ready = ensure_model_ready()

    try:
        # Step 1: NLP on comments (updates Comment.weak_signal + sentiment in DB)
        run.step = "Analyse NLP des commentaires"
        run.save(update_fields=["step"])
        comment_stats = analyze_comments(project.comments.all())

        # Step 2: Extract features + score each task
        run.step = "Scoring XGBoost par tâche"
        run.save(update_fields=["step"])
        project_features = extract_project_features(project)
        comment_signals = extract_comment_signals(project.comments.all())

        alerts: list[dict] = []
        task_scores: list[dict] = []
        for task in project.tasks.all():
            features = build_feature_vector(task, project_features, comment_signals)
            score = predict(features)
            factors = explain(features, FEATURE_NAMES)
            task_scores.append({
                "task_id": task.id,
                "task_title": task.title,
                "risk_score": round(score, 3),
                "factors": factors,
            })
            if score >= ALERT_THRESHOLD:
                severity = "CRITICAL" if score >= HIGH_ALERT_THRESHOLD else "WARNING"
                # Determine risk category from top factor
                category = _category_from_factors(factors)
                alert = {
                    "task_id": task.id,
                    "task_title": task.title,
                    "category": category,
                    "severity": severity,
                    "score": int(score * 100),
                    "title": f"Risque détecté sur « {task.title[:60]} »",
                    "factors": factors,
                    "recommendation": _recommendation(category, score),
                }
                alerts.append(alert)

        # Step 3: Create RiskAlert records (replace previous open alerts)
        run.step = "Création des alertes"
        run.save(update_fields=["step"])
        project.risk_alerts.all().delete()
        for a in alerts:
            task = project.tasks.filter(pk=a["task_id"]).first()
            RiskAlert.objects.create(
                project=project,
                task=task,
                category=a["category"],
                severity=a["severity"],
                score=a["score"],
                title=a["title"],
                description=a["recommendation"],
                factors=a["factors"],
            )

        # Step 4: Project-level risk score (max of task scores, with weights)
        project_risk = max((s["risk_score"] for s in task_scores), default=0.0)
        project.risk_score = round(project_risk, 3)
        if project_risk >= HIGH_ALERT_THRESHOLD:
            project.health = "CRITICAL"
        elif project_risk >= ALERT_THRESHOLD:
            project.health = "AT_RISK"
        elif project_risk >= 0.3:
            project.health = "WATCH"
        else:
            project.health = "HEALTHY"
        project.save(update_fields=["risk_score", "health"])

        # Step 5: Update the run
        finished = timezone.now()
        latency_ms = int((finished - started).total_seconds() * 1000)
        run.status = AgentRun.Status.SUCCEEDED
        run.step = f"{len(alerts)} alertes créées, score projet {int(project_risk * 100)}%"
        run.output_payload = {
            "risk_score": round(project_risk, 3),
            "alerts": alerts,
            "task_scores": task_scores,
            "comment_stats": comment_stats,
            "project_health": project.health,
            "model_used": "xgboost-v1" if model_ready else "rule-based",
        }
        run.latency_ms = latency_ms
        run.finished_at = finished
        run.save(update_fields=["status", "step", "output_payload", "latency_ms", "finished_at"])

        # Agent observability
        agent = run.agent
        agent.total_runs = (agent.total_runs or 0) + 1
        agent.successful_runs = (agent.successful_runs or 0) + 1
        agent.last_run_at = finished
        if agent.avg_latency_ms:
            agent.avg_latency_ms = int((agent.avg_latency_ms + latency_ms) / 2)
        else:
            agent.avg_latency_ms = latency_ms
        agent.save(update_fields=["total_runs", "successful_runs", "last_run_at", "avg_latency_ms"])

        _audit(run, correlation_id, project_risk, alerts, comment_stats, model_ready)
        _notify(run, project_risk, alerts)

        return {
            "status": "SUCCEEDED",
            "output": run.output_payload,
            "latency_ms": latency_ms,
            "engine": "xgboost-v1" if model_ready else "rule-based",
        }

    except Exception as e:
        logger.exception("Risk agent failed for run %s: %s", run.id, e)
        run.status = AgentRun.Status.FAILED
        run.error_message = str(e)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at"])
        return {"status": "FAILED", "error": str(e), "output": {}}


def _category_from_factors(factors: list[dict]) -> str:
    """Map the top factor label to a risk category."""
    if not factors:
        return "DELAY"
    top = factors[0]["label"]
    mapping = {
        "overdue_days": "DELAY",
        "is_blocked": "BLOCKER",
        "effort_variance": "QUALITY",
        "is_overdue": "DELAY",
        "comment_weak_signal_ratio": "QUALITY",
        "comment_blocked_count": "BLOCKER",
        "comment_waiting_count": "BLOCKER",
        "comment_regression_count": "QUALITY",
        "project_blocked_ratio": "LOAD",
        "project_overdue_ratio": "DELAY",
        "project_avg_progress": "DELAY",
    }
    return mapping.get(top, "DELAY")


def _recommendation(category: str, score: float) -> str:
    """Generate a recommendation message for a risk alert."""
    recommendations = {
        "DELAY": "Ré-estimer le reste à faire et envisager un découpage supplémentaire ou une réallocation.",
        "BLOCKER": "Identifier le dépendance bloquante et escalating auprès du chef de projet.",
        "QUALITY": "Mettre en place une revue de code renforcée et des tests supplémentaires.",
        "LOAD": "Rééquilibrer la charge — envisager de réaffecter ou d'ajouter des ressources.",
        "SCOPE": "Cadrer le périmètre avec le client et geler les nouveaux besoins.",
        "BUDGET": "Réviser le budget avec le sponsor et ajuster le scope si nécessaire.",
    }
    base = recommendations.get(category, "Suivre ce risque en comité projet.")
    return f"Score {int(score * 100)}/100. {base}"


def _audit(run, correlation_id, project_risk, alerts, comment_stats, model_ready):
    AuditLog.objects.create(
        actor=run.triggered_by,
        action=AuditLog.Action.AGENT_RUN,
        severity=AuditLog.Severity.WARNING if alerts else AuditLog.Severity.NOTICE,
        entity_type="Project",
        entity_id=str(run.project.pk),
        entity_label=run.project.name,
        description=(
            f"Agent 3 (Risk) — score projet {int(project_risk * 100)}%, "
            f"{len(alerts)} alertes créées. "
            f"Modèle: {'XGBoost' if model_ready else 'rule-based'}. "
            f"Signaux faibles détectés dans {comment_stats.get('with_signals', 0)}/"
            f"{comment_stats.get('total', 0)} commentaires."
        ),
        agent_key="RISK",
        run=run,
        correlation_id=correlation_id,
        metadata={
            "project_risk_score": round(project_risk, 3),
            "alerts_count": len(alerts),
            "model_used": "xgboost-v1" if model_ready else "rule-based",
            "comment_stats": comment_stats,
        },
    )


def _notify(run, project_risk, alerts):
    level = Notification.Level.ERROR if project_risk >= HIGH_ALERT_THRESHOLD else Notification.Level.WARNING
    title = f"Risque {'critique' if project_risk >= HIGH_ALERT_THRESHOLD else 'détecté'} — {run.project.name}"
    message = (
        f"Score de risque projet: {int(project_risk * 100)}%. "
        f"{len(alerts)} alerte(s) créée(s). "
        f"Consultez l'onglet Risques."
    )
    Notification.objects.create(
        user=run.triggered_by,
        category=Notification.Category.RISK,
        level=level,
        title=title,
        message=message,
        link=f"/app/projects/{run.project.pk}/risks",
        entity_type="Project",
        entity_id=run.project.pk,
        metadata={"agent": "RISK", "risk_score": round(project_risk, 3), "alerts_count": len(alerts)},
    )
