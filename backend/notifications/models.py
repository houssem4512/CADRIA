from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    Notification in-app. `user` null = diffusion globale (annonce admin) :
    dans ce cas la notification est matérialisée par ligne et reste
    consultable par tous, le flag `is_broadcast` porte la sémantique.
    """

    class Level(models.TextChoices):
        INFO = "INFO", "Information"
        SUCCESS = "SUCCESS", "Succès"
        WARNING = "WARNING", "Avertissement"
        ERROR = "ERROR", "Erreur"
        AGENT = "AGENT", "Agent"

    class Category(models.TextChoices):
        SYSTEM = "SYSTEM", "Système"
        AGENT = "AGENT", "Agent"
        RISK = "RISK", "Risque"
        TASK = "TASK", "Tâche"
        TEAM = "TEAM", "Équipe"
        VALIDATION = "VALIDATION", "Validation"
        ACCOUNT = "ACCOUNT", "Compte"
        INTEGRATION = "INTEGRATION", "Intégration"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    is_broadcast = models.BooleanField("diffusion globale", default=False)
    target_role = models.CharField(
        "rôle cible",
        max_length=20,
        blank=True,
        choices=[("ALL", "Tous"), ("ADMIN", "Administrateurs"), ("PM", "Chefs de projet"),
                 ("MEMBER", "Membres d'équipe"), ("VIEWER", "Observateurs")],
        default="ALL",
    )
    category = models.CharField(max_length=16, choices=Category.choices, default=Category.SYSTEM)
    level = models.CharField(max_length=10, choices=Level.choices, default=Level.INFO)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    link = models.CharField("route front", max_length=240, blank=True)
    entity_type = models.CharField(max_length=40, blank=True)
    entity_id = models.PositiveBigIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    archived = models.BooleanField(default=False)
    starred = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "notification"
        verbose_name_plural = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "read", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.title}"


class NotificationRead(models.Model):
    """État de lecture individuel pour les notifications diffusées."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("notification", "user")
        verbose_name = "lecture de notification"
        verbose_name_plural = "lectures de notifications"


class NotificationPreference(models.Model):
    """Canaux / fréquences par type d'évènement (vue Réglages)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_prefs"
    )
    in_app = models.BooleanField(default=True)
    email = models.BooleanField(default=True)
    slack = models.BooleanField(default=False)
    digest_frequency = models.CharField(
        max_length=12,
        choices=[("REALTIME", "Temps réel"), ("DAILY", "Quotidien"), ("WEEKLY", "Hebdomadaire")],
        default="REALTIME",
    )
    quiet_hours_start = models.TimeField(null=True, blank=True)
    quiet_hours_end = models.TimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "préférence de notification"
        verbose_name_plural = "préférences de notification"

    def __str__(self):
        return f"Préférences · {self.user}"
