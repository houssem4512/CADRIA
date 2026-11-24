"""
Test script — verifies MLflow is working correctly.
Run: python test_mlflow.py
"""
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

print("=" * 60)
print("MLflow Test Script")
print("=" * 60)

# 1. Check MLflow is installed
try:
    import mlflow
    print(f"✓ MLflow version: {mlflow.__version__}")
except ImportError:
    print("✗ MLflow not installed! Run: pip install mlflow")
    sys.exit(1)

# 2. Check tracking URI
from orchestration.mlops.tracking import TRACKING_URI, MLFLOW_OK, _DB_FILE
print(f"✓ MLflow available: {MLFLOW_OK}")
print(f"✓ Tracking URI: {TRACKING_URI}")
print(f"✓ Database file: {_DB_FILE}")
print(f"  DB exists: {os.path.exists(_DB_FILE)}")

# 3. Create a test run
print("\nCreating test run in MLflow...")
try:
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("cadria-agents")

    with mlflow.start_run(run_name="TEST-RUN"):
        mlflow.log_param("test", "hello from test script")
        mlflow.log_param("agent_key", "TEST")
        mlflow.log_metric("test_score", 99.9)
        mlflow.log_metric("latency_ms", 100)
        mlflow.set_tag("agent", "TEST")
        mlflow.set_tag("status", "SUCCEEDED")

    print("✓ Test run created successfully!")
except Exception as e:
    print(f"✗ Failed to create test run: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Test the log_agent_run function
print("\nTesting log_agent_run()...")
try:
    from orchestration.mlops.tracking import log_agent_run
    log_agent_run(
        agent_key="SCOPING",
        run_id=999,
        project_id=1,
        project_name="test-project",
        status="SUCCEEDED",
        latency_ms=4200,
        metrics={
            "tokens_in": 850,
            "tokens_out": 3200,
            "confidence": 0.78,
            "tasks_count": 32,
        },
        params={
            "model": "llama-3.3-70b-versatile",
            "engine": "groq-llm",
        },
        artifacts={
            "proposal": {"title": "Test Plan", "tasks": 32},
        },
    )
    print("✓ log_agent_run() succeeded!")
except Exception as e:
    print(f"✗ log_agent_run() failed: {e}")
    import traceback
    traceback.print_exc()

# 5. Verify the run appears
print("\nVerifying runs in MLflow...")
try:
    from mlflow.tracking import MlflowClient
    client = MlflowClient(tracking_uri=TRACKING_URI)
    exp = client.get_experiment_by_name("cadria-agents")
    if exp:
        runs = client.search_runs([exp.experiment_id], max_results=10)
        print(f"✓ Found {len(runs)} runs in experiment 'cadria-agents'")
        for r in runs:
            print(f"  - {r.info.run_name} (status: {r.info.status})")
    else:
        print("✗ Experiment 'cadria-agents' not found")
except Exception as e:
    print(f"✗ Verification failed: {e}")

print("\n" + "=" * 60)
print("If you see ✓ for all steps, MLflow is working!")
print("Now start MLflow UI with:")
print(f"  mlflow ui --backend-store-uri \"{TRACKING_URI}\" --host 0.0.0.0 --port 5000")
print("=" * 60)
