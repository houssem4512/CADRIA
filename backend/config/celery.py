"""
Celery configuration for the Cadria backend.

Used by Agent 3 (Risk) to run weekly on all active projects.

Broker: Django DB (simplest setup — no Redis needed for dev)
Result backend: Django DB

To enable in production, switch to Redis:
  CELERY_BROKER_URL = "redis://localhost:6379/0"
  CELERY_RESULT_BACKEND = "redis://localhost:6379/0"

This file is safe to import even if celery is not installed — the app
object will be None and tasks will run as regular functions.
"""
import os
import logging

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

try:
    from celery import Celery
    app = Celery("cadria")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.autodiscover_tasks()

    @app.task(bind=True)
    def debug_task(self):
        print(f"Request: {self.request!r}")

except ImportError:
    logger.info("Celery not installed — scheduling disabled (agents still work on demand)")
    app = None
