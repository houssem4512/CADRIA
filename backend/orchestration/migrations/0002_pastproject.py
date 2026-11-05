"""
Migration for the PastProject model (RAG store for Agent 1).
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("orchestration", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PastProject",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("brief", models.TextField(max_length=1000, verbose_name="brief du projet")),
                ("embedding", models.TextField(blank=True, default="", verbose_name="embedding (JSON array)")),
                ("lots_payload", models.JSONField(blank=True, default=list)),
                ("tasks_count", models.PositiveIntegerField(default=0)),
                ("total_estimate_hours", models.DecimalField(decimal_places=1, default=0, max_digits=9)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "proposal",
                    models.OneToOneField(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="past_project",
                        to="orchestration.proposal",
                    ),
                ),
            ],
            options={
                "verbose_name": "projet passé (RAG)",
                "verbose_name_plural": "projets passés (RAG)",
                "ordering": ["-created_at"],
            },
        ),
    ]
