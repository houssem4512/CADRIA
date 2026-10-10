from django.conf import settings
from django.db import models
from django.utils import timezone


class Project(models.Model):
    """Projet piloté par le copilote Cadria."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SCOPING = "SCOPING", "Cadrage"
        PLANNED = "PLANNED", "Planifié"
        ACTIVE = "ACTIVE", "En cours"
        AT_RISK = "AT_RISK", "À risque"
        ON_HOLD = "ON_HOLD", "En pause"
        COMPLETED = "COMPLETED", "Terminé"
        CANCELLED = "CANCELLED", "Annulé"

    class Health(models.TextChoices):
        GREEN = "GREEN", "Sain"
        AMBER = "AMBER", "À surveiller"
        RED = "RED", "Critique"

    class Methodology(models.TextChoices):
        SCRUM = "SCRUM", "Scrum / Sprints"
        KANBAN = "KANBAN", "Kanban (flux)"
        WATERFALL = "WATERFALL", "Cycle en V / Cascade"
        HYBRID = "HYBRID", "Hybride"

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    reference = models.CharField("référence", max_length=24, unique=True, editable=False, db_index=True)
    summary = models.CharField(max_length=280, blank=True)
    brief = models.TextField("description en langage naturel", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    health = models.CharField(max_length=10, choices=Health.choices, default=Health.GREEN, db_index=True)
    methodology = models.CharField(max_length=20, choices=Methodology.choices, default=Methodology.SCRUM)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_projects"
    )
    team = models.ForeignKey(
        "accounts.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="projects"
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="projects", blank=True
    )

    start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EUR")

    estimated_effort_hours = models.DecimalField(max_digits=9, decimal_places=1, default=0)
    spent_effort_hours = models.DecimalField(max_digits=9, decimal_places=1, default=0)
    progress = models.PositiveSmallIntegerField("avancement %", default=0)
    risk_score = models.DecimalField("score de risque", max_digits=5, decimal_places=2, default=0)

    # Référence vers l'outil externe (rempli par l'Agent 2)
    external_provider = models.CharField(max_length=20, blank=True, choices=[("JIRA", "Jira"), ("TRELLO", "Trello")])
    external_key = models.CharField(max_length=40, blank=True)
    external_url = models.URLField(blank=True)
    synced_at = models.DateTimeField(null=True, blank=True)

    tags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "projet"
        verbose_name_plural = "projets"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        from django.utils.text import slugify

        if not self.slug:
            base = slugify(self.name)[:180] or "projet"
            slug, i = base, 1
            while Project.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                i += 1
                slug = f"{base}-{i}"
            self.slug = slug
        if not self.reference:
            super().save(*args, **kwargs)
            self.reference = f"PRJ-{self.pk:04d}"
            kwargs.pop("force_insert", None)
            super().save(update_fields=["reference"])
            return
        super().save(*args, **kwargs)

    # --- Derived metrics -------------------------------------------------
    @property
    def tasks(self):
        return self.task_set

    @property
    def total_tasks(self):
        return self.tasks.count()

    @property
    def done_tasks(self):
        return self.tasks.filter(status=Task.Status.DONE).count()

    @property
    def overdue_tasks(self):
        return self.tasks.filter(due_date__lt=timezone.now().date()).exclude(status=Task.Status.DONE).count()

    @property
    def blocked_tasks(self):
        return self.tasks.filter(blocked=True).exclude(status=Task.Status.DONE).count()

    @property
    def is_late(self):
        return bool(self.target_end_date and self.target_end_date < timezone.now().date()
                    and self.status not in (self.Status.COMPLETED, self.Status.CANCELLED))

    @property
    def budget_consumed(self):
        if not self.budget:
            return 0
        consumed = sum(float(t.cost) for t in self.tasks.all())
        return round(consumed / float(self.budget) * 100, 1) if self.budget else 0


class WorkPackage(models.Model):
    """Lot de travail issu du découpage (Agent 1)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="work_packages")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    color = models.CharField(max_length=9, default="#2563EB")
    estimated_effort_hours = models.DecimalField(max_digits=8, decimal_places=1, default=0)
    confidence = models.DecimalField("confiance estimation", max_digits=4, decimal_places=2, default=0)
    external_id = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "lot de travail"
        verbose_name_plural = "lots de travail"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.project.reference} · {self.name}"

    @property
    def task_count(self):
        return self.tasks.count()


class Sprint(models.Model):
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planifié"
        ACTIVE = "ACTIVE", "Actif"
        COMPLETED = "COMPLETED", "Terminé"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sprints")
    name = models.CharField(max_length=120)
    goal = models.TextField("objectif de sprint", blank=True)
    order = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    committed_points = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    completed_points = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    capacity_hours = models.DecimalField(max_digits=7, decimal_places=1, default=0)
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    external_id = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "sprint"
        verbose_name_plural = "sprints"
        ordering = ["order", "id"]
        unique_together = ("project", "name")

    def __str__(self):
        return f"{self.project.reference} · {self.name}"

    @property
    def velocity(self):
        return float(self.completed_points)


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "À faire"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        REVIEW = "REVIEW", "En revue"
        BLOCKED = "BLOCKED", "Bloquée"
        DONE = "DONE", "Terminée"

    class Priority(models.TextChoices):
        LOWEST = "LOWEST", "Très basse"
        LOW = "LOW", "Basse"
        MEDIUM = "MEDIUM", "Moyenne"
        HIGH = "HIGH", "Haute"
        HIGHEST = "HIGHEST", "Critique"

    class Type(models.TextChoices):
        FEATURE = "FEATURE", "Fonctionnalité"
        BUG = "BUG", "Bug"
        TECH = "TECH", "Dette technique"
        SPIKE = "SPIKE", "Spike / Étude"
        DOC = "DOC", "Documentation"
        TEST = "TEST", "Test"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    work_package = models.ForeignKey(
        WorkPackage, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    sprint = models.ForeignKey(
        Sprint, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    task_type = models.CharField(max_length=16, choices=Type.choices, default=Type.FEATURE)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TODO, db_index=True)

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_tasks",
    )

    estimate_hours = models.DecimalField("charge estimée (h)", max_digits=7, decimal_places=1, default=0)
    spent_hours = models.DecimalField("charge réalisée (h)", max_digits=7, decimal_places=1, default=0)
    story_points = models.DecimalField(max_digits=6, decimal_places=1, default=0)

    required_skills = models.JSONField("compétences requises", default=list, blank=True)
    acceptance_criteria = models.JSONField("critères d'acceptation", default=list, blank=True)

    risk_score = models.DecimalField("score de risque", max_digits=5, decimal_places=2, default=0)
    risk_factors = models.JSONField("facteurs de risque", default=list, blank=True)
    risk_explanation = models.TextField(blank=True)

    blocked = models.BooleanField(default=False)
    blocked_reason = models.CharField(max_length=255, blank=True)
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    external_id = models.CharField(max_length=60, blank=True)
    external_url = models.URLField(blank=True)
    created_by_agent = models.BooleanField(default=False)
    labels = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "tâche"
        verbose_name_plural = "tâches"
        ordering = ["-priority", "created_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def __str__(self):
        return self.title

    @property
    def cost(self):
        rate = self.assignee.hourly_cost if self.assignee_id and self.assignee else 0
        return round(float(self.spent_hours) * float(rate or 0), 2)

    @property
    def effort_variance(self):
        est, spent = float(self.estimate_hours), float(self.spent_hours)
        if est <= 0:
            return 0
        return round((spent - est) / est * 100, 1)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < timezone.now().date() and self.status != self.Status.DONE)

    def save(self, *args, **kwargs):
        if self.status == self.Status.DONE and not self.completed_at:
            self.completed_at = timezone.now()
        if self.status != self.Status.DONE:
            self.completed_at = None
        super().save(*args, **kwargs)


class RiskAlert(models.Model):
    """Alerte produite par l'Agent 3 (analyse & suivi des risques)."""

    class Severity(models.TextChoices):
        INFO = "INFO", "Information"
        WARNING = "WARNING", "Avertissement"
        CRITICAL = "CRITICAL", "Critique"

    class Category(models.TextChoices):
        DELAY = "DELAY", "Risque de retard"
        QUALITY = "QUALITY", "Risque qualité"
        LOAD = "LOAD", "Dérive de charge"
        BLOCKER = "BLOCKER", "Blocage"
        SCOPE = "SCOPE", "Dérive de périmètre"
        BUDGET = "BUDGET", "Dérive budgétaire"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="risk_alerts")
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_alerts")
    sprint = models.ForeignKey(Sprint, on_delete=models.SET_NULL, null=True, blank=True, related_name="risk_alerts")
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.DELAY)
    severity = models.CharField(max_length=12, choices=Severity.choices, default=Severity.WARNING)
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    factors = models.JSONField("facteurs contributeurs", default=list, blank=True)
    recommendation = models.TextField(blank=True)
    acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ack_alerts"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "alerte de risque"
        verbose_name_plural = "alertes de risque"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"[{self.severity}] {self.title}"


class Integration(models.Model):
    """Configuration du connecteur Jira / Trello (utilisé par l'Agent 2)."""

    class Provider(models.TextChoices):
        JIRA = "JIRA", "Jira"
        TRELLO = "TRELLO", "Trello"
        GITHUB = "GITHUB", "GitHub"

    class Status(models.TextChoices):
        DISCONNECTED = "DISCONNECTED", "Déconnecté"
        CONNECTED = "CONNECTED", "Connecté"
        ERROR = "ERROR", "Erreur"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="integrations"
    )
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, null=True, blank=True, related_name="integrations"
    )
    provider = models.CharField(max_length=12, choices=Provider.choices, default=Provider.JIRA)
    name = models.CharField(max_length=120, default="Instance principale")
    base_url = models.URLField(blank=True)
    board_key = models.CharField("projet / board", max_length=60, blank=True)
    workspace = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DISCONNECTED)
    last_error = models.TextField(blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    auto_sync = models.BooleanField(default=True)
    sync_interval_minutes = models.PositiveIntegerField(default=60)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "intégration"
        verbose_name_plural = "intégrations"
        ordering = ["provider", "name"]

    def __str__(self):
        return f"{self.provider} · {self.name}"


class Comment(models.Model):
    """Commentaire projet/tâche — source de signaux faibles pour l'Agent 3."""

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="comments")
    task = models.ForeignKey(
        Task, on_delete=models.CASCADE, null=True, blank=True, related_name="comments"
    )
    body = models.TextField()
    sentiment = models.CharField(
        max_length=12,
        choices=[("POSITIVE", "Positif"), ("NEUTRAL", "Neutre"), ("NEGATIVE", "Négatif")],
        default="NEUTRAL",
    )
    weak_signal = models.BooleanField("signal faible détecté", default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "commentaire"
        verbose_name_plural = "commentaires"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} · {self.created_at:%d/%m/%Y}"
