from django.contrib import admin
from .models import Notification, NotificationRead, NotificationPreference

admin.site.register(Notification)
admin.site.register(NotificationRead)
admin.site.register(NotificationPreference)
