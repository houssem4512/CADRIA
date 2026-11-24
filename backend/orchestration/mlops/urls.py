"""
URL routes for MLOps metrics endpoints.

Add these to your existing orchestration/urls.py:

    from .mlops.metrics_views import (
        MetricsOverviewView,
        MetricsAgentDetailView,
        MetricsTimelineView,
        MetricsMlflowLogView,
    )

    urlpatterns = [
        # ... existing routes ...
        path("metrics/", MetricsOverviewView.as_view(), name="metrics-overview"),
        path("metrics/agents/<str:agent_key>/", MetricsAgentDetailView.as_view(), name="metrics-agent-detail"),
        path("metrics/timeline/", MetricsTimelineView.as_view(), name="metrics-timeline"),
        path("metrics/mlflow/", MetricsMlflowLogView.as_view(), name="metrics-mlflow-log"),
    ] + router.urls
"""
from django.urls import path
from .metrics_views import (
    MetricsOverviewView,
    MetricsAgentDetailView,
    MetricsTimelineView,
    MetricsMlflowLogView,
)

# These routes should be MERGED into orchestration/urls.py
metrics_urlpatterns = [
    path("metrics/", MetricsOverviewView.as_view(), name="metrics-overview"),
    path("metrics/agents/<str:agent_key>/", MetricsAgentDetailView.as_view(), name="metrics-agent-detail"),
    path("metrics/timeline/", MetricsTimelineView.as_view(), name="metrics-timeline"),
    path("metrics/mlflow/", MetricsMlflowLogView.as_view(), name="metrics-mlflow-log"),
]
