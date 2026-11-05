from django.urls import path

from .views import AdminDashboardView, ClientDashboardView, PlatformInsightsView

urlpatterns = [
    path("analytics/dashboard/", ClientDashboardView.as_view(), name="analytics-dashboard"),
    path("analytics/admin/", AdminDashboardView.as_view(), name="analytics-admin"),
    path("analytics/insights/", PlatformInsightsView.as_view(), name="analytics-insights"),
]
