from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet, AuditSummaryView

router = DefaultRouter()
router.register(r"audit", AuditLogViewSet, basename="auditlog")

# La route littérale doit précéder le routeur : sinon `audit/summary/` est
# capturée par la route de détail `audit/<pk>/`.
urlpatterns = [
    path("audit/summary/", AuditSummaryView.as_view(), name="audit-summary"),
] + router.urls
