"""
Espace réservé aux agents.

Aucun agent n'est implémenté ici : ce module décrit uniquement le contrat
(définitions d'agents, exécutions, propositions, assignations) que les agents
devront respecter une fois branchés. Le backend orchestre, journalise et
expose les résultats ; l'inférence est déléguée à un runtime externe.
"""
from django.conf import settings
from django.db import models


class AgentDefinition(models.Model):
    """Fiche d'identité d'un agent du système multi-agents."""

    class Kind(models.TextChoices):
        SCOPING = "SCOPING", "Agent 1 — Cadrage & décomposition"
        OPS = "OPS", "Agent 2 — Intégration Jira/Trello & assignation"
        RISK = "RISK", "Agent 3 — Analyse & suivi des risques"
        ORCHESTRATOR = "ORCHESTRATOR", "Orchestrateur"

    class State(models.TextChoices):
        RESERVED = "RESERVED", "Emplacement réservé"
        BETA = "BETA", "Bêta"
        ENABLED = "ENABLED", "Actif"
        DISABLED = "DISABLED", "Désactivé"

    key = models.CharField(max_length=20, choices=Kind.choices, unique=True)
    name = models.CharField(max_length=120)
    short_name = models.CharField(max_length=40, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=40, default="sparkles")
    color = models.CharField(max_length=9, default="#2563EB")
    state = models.CharField(max_length=12, choices=State.choices, default=State.RESERVED)

    # Suggested stack (documentation only — from the specification)
    suggested_model = models.CharField(max_length=160, blank=True)
    suggested_stack = models.CharField(max_length=240, blank=True)
    runtime_endpoint = models.URLField("endpoint du runtime", blank=True)
    requires_human_validation = models.BooleanField(default=False)

    capabilities = models.JSONField(default=list, blank=True)
    input_schema_hint = models.JSONField(default=dict, blank=True)
    output_schema_hint = models.JSONField(default=dict, blank=True)

    # Observability (fed by the Grafana-style dashboard)
    total_runs = models.PositiveIntegerField(default=0)
    successful_runs = models.PositiveIntegerField(default=0)
    failed_runs = models.PositiveIntegerField(default=0)
    avg_latency_ms = models.PositiveIntegerField(default=0)
    last_run_at = models.DateTimeField(null=True, blank=True)

    order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "définition d'agent"
        verbose_name_plural = "définitions d'agents"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    @property
    def success_rate(self):
        if not self.total_runs:
            return 0
        return round(self.successful_runs / self.total_runs * 100, 1)

    @property
    def is_available(self):
        return self.state in (self.State.ENABLED, self.State.BETA)


class AgentRun(models.Model):
    """Une exécution d'agent (traçabilité complète pour le journal d'audit)."""

    class Status(models.TextChoices):
        QUEUED = "QUEUED", "En file"
        RUNNING = "RUNNING", "En cours"
        AWAITING_VALIDATION = "AWAITING_VALIDATION", "En attente de validation"
        SUCCEEDED = "SUCCEEDED", "Succès"
        FAILED = "FAILED", "Échec"
        CANCELLED = "CANCELLED", "Annulé"
        SKIPPED = "SKIPPED", "Ignoré (runtime non branché)"

    class Trigger(models.TextChoices):
        MANUAL = "MANUAL", "Lancement manuel"
        PIPELINE = "PIPELINE", "Pipeline automatique"
        SCHEDULED = "SCHEDULED", "Planifié (Airflow)"
        RETRY = "RETRY", "Nouvelle tentative"

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="agent_runs"
    )
    agent = models.ForeignKey(AgentDefinition, on_delete=models.CASCADE, related_name="runs")
    parent_run = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_runs"
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_runs"
    )
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.MANUAL)

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.QUEUED, db_index=True)
    step = models.CharField("étape courante", max_length=120, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)

    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    tokens_in = models.PositiveIntegerField(default=0)
    tokens_out = models.PositiveIntegerField(default=0)
    cost_estimate = models.DecimalField(max_digits=10, decimal_places=4, default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "exécution d'agent"
        verbose_name_plural = "exécutions d'agents"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.agent.short_name or self.agent.name} · {self.project.reference} · {self.status}"

    @property
    def duration_display(self):
        if self.latency_ms:
            return f"{self.latency_ms / 1000:.2f} s"
        return "—"


class Proposal(models.Model):
    """
    Plan proposé par l'Agent 1 (lots / tâches / estimations) — soumis à la
    validation humaine avant toute écriture dans Jira ou Trello.
    """

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        PENDING = "PENDING", "En attente de validation"
        APPROVED = "APPROVED", "Approuvé"
        REJECTED = "REJECTED", "Rejeté"
        APPLIED = "APPLIED", "Appliqué à l'outil externe"

    run = models.OneToOneField(
        AgentRun, on_delete=models.CASCADE, related_name="proposal", null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="proposals"
    )
    title = models.CharField(max_length=200, default="Plan de découpage proposé")
    summary = models.TextField(blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)

    version = models.PositiveIntegerField(default=1)
    lots_payload = models.JSONField("lots proposés", default=list, blank=True)
    tasks_payload = models.JSONField("tâches proposées", default=list, blank=True)
    sprints_payload = models.JSONField("sprints proposés", default=list, blank=True)
    risks_payload = models.JSONField("risques identifiés", default=list, blank=True)
    assumptions = models.JSONField("hypothèses", default=list, blank=True)

    total_estimate_hours = models.DecimalField(max_digits=9, decimal_places=1, default=0)
    confidence = models.DecimalField("score de complétude", max_digits=4, decimal_places=2, default=0)
    estimated_end_date = models.DateField(null=True, blank=True)

    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="validated_proposals"
    )
    validated_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "proposition de plan"
        verbose_name_plural = "propositions de plan"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project.reference} · {self.title} (v{self.version})"

    @property
    def tasks_count(self):
        return len(self.tasks_payload or [])

    @property
    def lots_count(self):
        return len(self.lots_payload or [])


class AssignmentSuggestion(models.Model):
    """Assignation suggérée par l'Agent 2 (matching compétences + charge)."""

    proposal = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name="assignments")
    task_ref = models.CharField("référence tâche proposée", max_length=80)
    task_title = models.CharField(max_length=200, blank=True)
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="suggested_assignments"
    )
    match_score = models.DecimalField("score de matching", max_digits=4, decimal_places=3, default=0)
    rationale = models.TextField("explication", blank=True)
    matched_skills = models.JSONField(default=list, blank=True)
    workload_before_hours = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    workload_after_hours = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    accepted = models.BooleanField(null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "suggestion d'assignation"
        verbose_name_plural = "suggestions d'assignation"
        ordering = ["-match_score"]

    def __str__(self):
        return f"{self.task_ref} → {self.candidate} ({self.match_score})"

    @property
    def load_delta(self):
        return float(self.workload_after_hours) - float(self.workload_before_hours)
