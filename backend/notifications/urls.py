from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BroadcastView, NotificationPreferenceView, NotificationViewSet

router = DefaultRouter()
router.register(r"notifications", NotificationViewSet, basename="notification")

# Routes littérales avant le routeur : sinon `notifications/preferences/` est
# capturé par la route de détail `notifications/<pk>/`.
urlpatterns = [
    path("notifications/broadcast/", BroadcastView.as_view(), name="notification-broadcast"),
    path("notifications/preferences/", NotificationPreferenceView.as_view(), name="notification-prefs"),
] + router.urls
