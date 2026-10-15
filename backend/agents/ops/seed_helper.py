"""Charge les données de démo dans les tests, même plusieurs fois dans le même processus."""
import copy
from unittest.mock import patch

from django.core.management import call_command

from accounts.management.commands import seed_demo

# seed_demo vide (pop) la liste AGENTS au premier appel : on en garde une copie intacte.
_AGENTS_ORIGINAL = copy.deepcopy(seed_demo.AGENTS)


def seed_demo_data():
    with patch.object(seed_demo, "AGENTS", copy.deepcopy(_AGENTS_ORIGINAL)):
        call_command("seed_demo", verbosity=0)