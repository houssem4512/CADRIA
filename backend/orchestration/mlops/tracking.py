"""
SIMPLIFIED MLflow tracking — direct, no-fail approach.
"""
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import MLflow
try:
    import mlflow
    MLFLOW_OK = True
except ImportError:
    MLFLOW_OK = False
    logger.warning("MLflow not installed! Run: pip install mlflow")

# Use ABSOLUTE path to the database
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DB_FILE = os.path.join(_BACKEND_DIR, "mlflow.db")
TRACKING_URI = f"sqlite:///{_DB_FILE}"

if MLFLOW_OK:
    try:
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment("cadria-agents")
        logger.info("MLflow ready: %s", TRACKING_URI)
    except Exception as e:
        logger.error("MLflow setup FAILED: %s", e)
        MLFLOW_OK = False

# JSONL log file (same directory)
LOG_FILE = os.path.join(_BACKEND_DIR, "agent_metrics.jsonl")


def log_agent_run(agent_key, run_id, project_id, project_name="", status="SUCCEEDED",
                  latency_ms=0, metrics=None, params=None, artifacts=None):
    """Log to MLflow + JSONL file. Never raises exceptions."""
    metrics = metrics or {}
    params = params or {}
    artifacts = artifacts or {}

    # Ensure standard fields
    metrics["latency_ms"] = latency_ms
    params["agent_key"] = agent_key
    params["project_name"] = project_name
    params["run_id"] = str(run_id or "")
    params["timestamp"] = datetime.now().isoformat()

    # 1. Write to JSONL (always works)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "timestamp": params["timestamp"],
                "agent_key": agent_key,
                "project_name": project_name,
                "status": status,
                "latency_ms": latency_ms,
                "metrics": metrics,
            }, default=str) + "\n")
    except Exception as e:
        logger.warning("JSONL write failed: %s", e)

    # 2. Log to MLflow
    if not MLFLOW_OK:
        logger.warning("MLflow not available — skipping (agent=%s)", agent_key)
        return

    try:
        run_name = f"{agent_key}-{run_id or 'manual'}"
        with mlflow.start_run(run_name=run_name):
            # Log params
            for k, v in params.items():
                mlflow.log_param(k, str(v)[:250])

            # Log metrics (only numbers)
            for k, v in metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(k, float(v))

            # Log artifacts
            for name, data in artifacts.items():
                import tempfile
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
                json.dump(data, tmp, default=str, indent=2, ensure_ascii=False)
                tmp.close()
                mlflow.log_artifact(tmp.name, artifact_path=name)
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass

            # Tags
            mlflow.set_tag("agent", agent_key)
            mlflow.set_tag("status", status)
            mlflow.set_tag("project", project_name)

        logger.info("✓ MLflow run logged: %s #%s (%s)", agent_key, run_id, status)
    except Exception as e:
        logger.error("MLflow logging FAILED for %s: %s", agent_key, e)
        import traceback
        traceback.print_exc()


def read_metrics_log(limit=100):
    """Read recent metrics from JSONL file."""
    try:
        if not os.path.exists(LOG_FILE):
            return []
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [json.loads(line.strip()) for line in lines[-limit:] if line.strip()]
    except Exception:
        return []

