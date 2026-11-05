"""
One-time setup script for Cadria agents.

Run this ONCE after installing dependencies:
    python manage.py setup_agents

It does 3 things:
  1. Updates all AgentDefinition states from RESERVED → ENABLED
     (so the UI no longer shows "Emplacement réservé")
  2. Pre-downloads the sentence-transformers model (~118MB)
     (so the first RAG query doesn't timeout)
  3. Trains the XGBoost risk model on synthetic data
     (so Agent 3 has a model ready)
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "One-time setup: enable agents, pre-download models, train XGBoost"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Cadria agents setup ===\n"))

        # ── 1. Enable all agents ──────────────────────────────────────────
        self.stdout.write("\n[1/3] Enabling agents...")
        from orchestration.models import AgentDefinition
        updated = AgentDefinition.objects.filter(state="RESERVED").update(state="ENABLED")
        self.stdout.write(f"  ✅ {updated} agent(s) enabled (RESERVED → ENABLED)")

        for agent in AgentDefinition.objects.all():
            self.stdout.write(f"     · {agent.key}: {agent.state} — {agent.name[:50]}")

        # ── 2. Pre-download sentence-transformers model ───────────────────
        self.stdout.write("\n[2/3] Pre-downloading sentence-transformers model...")
        self.stdout.write("  (paraphrase-multilingual-MiniLM-L12-v2, ~118MB — first time only)")
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            vec = model.encode("test", normalize_embeddings=True)
            self.stdout.write(f"  ✅ Model loaded — embedding dimension: {vec.shape[0]}")
        except ImportError:
            self.stdout.write("  ⚠️  sentence-transformers not installed — RAG disabled")
            self.stdout.write("     Run: pip install sentence-transformers")
        except Exception as e:
            self.stdout.write(f"  ⚠️  Model load failed: {e}")
            self.stdout.write("     RAG will be skipped on first run")

        # ── 3. Train XGBoost risk model ───────────────────────────────────
        self.stdout.write("\n[3/3] Training XGBoost risk model...")
        try:
            from orchestration.risk.scorer import train_model
            path = train_model()
            if path:
                self.stdout.write(f"  ✅ Model trained and saved to: {path}")
            else:
                self.stdout.write("  ⚠️  XGBoost not installed — risk scorer uses rule-based fallback")
                self.stdout.write("     Run: pip install xgboost shap")
        except Exception as e:
            self.stdout.write(f"  ⚠️  Training failed: {e}")
            self.stdout.write("     Risk agent will use rule-based fallback")

        self.stdout.write("\n" + self.style.MIGRATE_HEADING("=== Setup complete ==="))
        self.stdout.write("\nNext steps:")
        self.stdout.write("  1. Restart: python manage.py runserver 0.0.0.0:8000")
        self.stdout.write("  2. Open project → Copilote → Launch Agent 1\n")