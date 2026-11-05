"""
Celery tasks for the orchestration app.

Currently:
  - run_risk_agent_all_projects: weekly task that runs Agent 3 on every ACTIVE project
  - train_risk_model: monthly task to retrain the XGBoost model on accumulated data

These tasks are only registered if Celery is installed. If not, the functions
still work as regular Python functions (callable directly, just not scheduled).
"""
import logging

logger = logging.getLogger(__name__)

# Try to import celery — if not installed, define a no-op decorator
try:
    from celery import shared_task
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.info("Celery not installed — tasks will run as regular functions")

    def shared_task(*args, **kwargs):
        """No-op decorator when celery isn't installed."""
        def decorator(func):
            func.delay = lambda *a, **k: func(*a, **k)
            return func
        if args and callable(args[0]):
            return decorator(args[0])
        return decorator


@shared_task(bind=True, name="cadria.run_risk_agent_all_projects")
def run_risk_agent_all_projects(self):
    """
    Weekly task: run Agent 3 (Risk) on every ACTIVE project.

    Scheduled via Celery beat (see config/settings.py::CELERY_BEAT_SCHEDULE).
    Can also be called directly:
        python manage.py shell -c "from orchestration.tasks import run_risk_agent_all_projects; run_risk_agent_all_projects()"
    """
    from orchestration.models import AgentDefinition, AgentRun
    from orchestration.risk.runner import run as risk_run
    from projects.models import Project

    try:
        risk_agent = AgentDefinition.objects.get(key="RISK")
    except AgentDefinition.DoesNotExist:
        logger.error("RISK agent definition not found — skipping weekly run")
        return {"error": "RISK agent not found"}

    active_projects = Project.objects.filter(status__in=["PLANNED", "ACTIVE", "AT_RISK"])
    results = []
    for project in active_projects:
        run = AgentRun.objects.create(
            project=project,
            agent=risk_agent,
            triggered_by=None,
            trigger=AgentRun.Trigger.SCHEDULED,
            status=AgentRun.Status.QUEUED,
            step="Planifié (Celery beat)",
            input_payload={"window_days": 30, "scheduled": True},
        )
        try:
            result = risk_run(run)
            results.append({"project": project.reference, "result": result})
        except Exception as e:
            logger.exception("Risk run failed for project %s: %s", project.reference, e)
            results.append({"project": project.reference, "error": str(e)})

    return {"runs": results, "total": len(results)}


@shared_task(name="cadria.train_risk_model_monthly")
def train_risk_model_monthly():
    """
    Monthly task: retrain the XGBoost risk model on accumulated outcome data.

    For v1, retrains on synthetic data (the rule-based bootstrap).
    For v2, would load real (features, actual_outcome) pairs from completed tasks.
    """
    from orchestration.risk.scorer import train_model
    path = train_model()
    logger.info("Monthly risk model retrain complete: %s", path)
    return {"model_path": path}


@shared_task(name="cadria.collect_jira_metrics_weekly")
def collect_jira_metrics_weekly():
    """
    Weekly task: pull Jira/GitHub metrics for all active projects.

    For v1, this is a stub — the metrics are already in Cadria's DB via the
    tasks + comments. For v2, this would call Jira REST API to sync.
    """
    logger.info("Jira metrics collection (stub — metrics already in DB)")
    return {"status": "stub"}