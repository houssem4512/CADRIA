"""Active ou désactive les agents Cadria existants."""
from django.conf import settings
from django.core.management.base import BaseCommand

from orchestration.models import AgentDefinition


class Command(BaseCommand):
    help = "Passe les agents au statut ENABLED (ou RESERVED avec --disable)."

    def add_arguments(self, parser):
        parser.add_argument("--disable", action="store_true",
                            help="Repasse les agents au statut RESERVED.")
        parser.add_argument("--endpoint", default="",
                            help="Endpoint HTTP commun (mode HTTP uniquement).")

    def handle(self, *args, **options):
        state = (AgentDefinition.State.RESERVED if options["disable"]
                 else AgentDefinition.State.ENABLED)
        updated = 0
        for agent in AgentDefinition.objects.exclude(key=AgentDefinition.Kind.ORCHESTRATOR):
            agent.state = state
            if options["endpoint"]:
                agent.runtime_endpoint = f"{options['endpoint'].rstrip('/')}/{agent.key.lower()}"
            agent.save(update_fields=["state", "runtime_endpoint"])
            updated += 1
        mode = settings.AGENT_RUNTIME.get("MODE", "LOCAL")
        self.stdout.write(self.style.SUCCESS(
            f"{updated} agent(s) en statut {state} · mode runtime {mode}"
        ))
