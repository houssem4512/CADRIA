from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom manager — email is the login identifier."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("status", User.Status.ACTIVE)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superuser doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superuser doit avoir is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Utilisateur de la plateforme Cadria.

    Rôles :
      * ADMIN  — administration de la plateforme (comptes, stats, supervision)
      * PM     — chef de projet (pilote ses projets, lance les agents)
      * MEMBER — membre d'équipe (consulte ses tâches / charge)
    """

    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Administrateur"
        PM = "PM", "Chef de projet"
        MEMBER = "MEMBER", "Membre d'équipe"
        VIEWER = "VIEWER", "Observateur"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Actif"
        PENDING = "PENDING", "En attente"
        SUSPENDED = "SUSPENDED", "Suspendu"

    username = None
    email = models.EmailField("adresse e-mail", unique=True, db_index=True)
    first_name = models.CharField("prénom", max_length=150, blank=True)
    last_name = models.CharField("nom", max_length=150, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PM, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField("poste", max_length=120, blank=True)
    avatar_color = models.CharField(max_length=9, default="#2563EB")
    bio = models.TextField(blank=True)
    company = models.CharField("organisation", max_length=150, blank=True)
    timezone = models.CharField(max_length=64, default="Europe/Paris")
    locale = models.CharField(max_length=8, default="fr")

    # Notification preferences
    notify_email = models.BooleanField(default=True)
    notify_push = models.BooleanField(default=True)
    notify_risk_alerts = models.BooleanField(default=True)
    notify_assignments = models.BooleanField(default=True)
    notify_agent_runs = models.BooleanField(default=True)
    notify_weekly_digest = models.BooleanField(default=False)

    weekly_capacity_hours = models.DecimalField(
        "capacité hebdomadaire (h)", max_digits=5, decimal_places=1, default=35.0
    )
    hourly_cost = models.DecimalField("coût horaire", max_digits=8, decimal_places=2, default=0)

    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"
        ordering = ["-created_at"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def full_name(self):
        return self.get_full_name() or self.email.split("@")[0]

    @property
    def initials(self):
        parts = [p for p in (self.first_name, self.last_name) if p]
        if not parts:
            return (self.email[:2] or "??").upper()
        return "".join(p[0] for p in parts[:2]).upper()

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_pm(self):
        return self.role == self.Role.PM

    def touch(self):
        self.last_seen_at = timezone.now()
        self.save(update_fields=["last_seen_at"])


class Skill(models.Model):
    """Compétence d'un membre — sert au matching de l'Agent 2 (tool-calling)."""

    name = models.CharField(max_length=80, unique=True)
    category = models.CharField(
        max_length=40,
        choices=[
            ("TECH", "Technique"),
            ("FUNC", "Fonctionnel"),
            ("DESIGN", "Design"),
            ("DATA", "Data / IA"),
            ("MGMT", "Management"),
        ],
        default="TECH",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "compétence"
        verbose_name_plural = "compétences"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class UserSkill(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name="holders")
    level = models.PositiveSmallIntegerField(
        "niveau (1-5)",
        default=3,
        choices=[(1, "1 · Notions"), (2, "2 · Débutant"), (3, "3 · Autonome"),
                 (4, "4 · Avancé"), (5, "5 · Expert")],
    )

    class Meta:
        unique_together = ("user", "skill")
        verbose_name = "compétence utilisateur"
        verbose_name_plural = "compétences utilisateur"

    def __str__(self):
        return f"{self.user} — {self.skill} ({self.level})"


class Team(models.Model):
    """Équipe projet — unité de base du pilotage de charge."""

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=9, default="#0EA5E9")
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="owned_teams")
    members = models.ManyToManyField(User, related_name="teams", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "équipe"
        verbose_name_plural = "équipes"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PasswordResetCode(models.Model):
    """Code à 6 chiffres envoyé par e-mail (démo : renvoyé dans la réponse API)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reset_codes")
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_valid(self):
        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"{self.user.email} · {self.code}"
