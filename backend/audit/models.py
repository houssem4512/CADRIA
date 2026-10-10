"""
Journal d'audit — trace qui a fait quoi, et quel agent a déclenché quelle action.
Exigence transverse du cahier des charges : coordination & traçabilité multi-agents.
"""
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        LOGIN = "LOGIN", "Connexion"
        LOGOUT = "LOGOUT", "Déconnexion"
        SIGNUP = "SIGNUP", "Inscription"
        VALIDATE = "VALIDATE", "Validation"
        REJECT = "REJECT", "Rejet"
        AGENT_RUN = "AGENT_RUN", "Exécution agent"
        AGENT_WRITE = "AGENT_WRITE", "Écriture externe"
        SYNC = "SYNC", "Synchronisation"
        EXPORT = "EXPORT", "Export"
        PERMISSION = "PERMISSION", "Permission"
        ALERT = "ALERT", "Alerte"

    class Severity(models.TextChoices):
        INFO = "INFO", "Information"
        NOTICE = "NOTICE", "Remarquable"
        WARNING = "WARNING", "Avertissement"
        CRITICAL = "CRITICAL", "Critique"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    actor_label = models.CharField(max_length=160, blank=True, help_text="Libellé si l'acteur est un agent ou un système")
    action = models.CharField(max_length=16, choices=Action.choices, default=Action.UPDATE)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.INFO)
    entity_type = models.CharField(max_length=60, blank=True)
    entity_id = models.CharField(max_length=60, blank=True)
    entity_label = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    changes = models.JSONField("diff", default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    # Traçabilité multi-agents
    agent_key = models.CharField(max_length=20, blank=True, db_index=True)
    run = models.ForeignKey(
        "orchestration.AgentRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    correlation_id = models.CharField(max_length=64, blank=True, db_index=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "entrée de journal"
        verbose_name_plural = "journal d'audit"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["entity_type", "entity_id"])]

    def __str__(self):
        return f"{self.action} · {self.entity_type} · {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def actor_display(self):
        return self.actor_label or (self.actor.full_name if self.actor else "Système")
