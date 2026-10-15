from abc import ABC, abstractmethod


class ProviderClient(ABC):
    """Interface commune : le reste du code ne sait pas si c'est Jira ou Trello."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.api_calls = 0

    @abstractmethod
    def create_sprint(self, name: str, goal: str = "") -> dict: ...

    @abstractmethod
    def create_task(self, container_id: str, task: dict) -> dict: ...

    @abstractmethod
    def assign(self, external_task_id: str, member_id: str) -> dict: ...

    def create_epic(self, name: str, description: str = ""):
        
        """Optionnel : renvoie {"id", "url"} si le fournisseur gère les epics, sinon None."""
        return None

    def list_members(self) -> list:
        """Optionnel : [{"id", "fullName"}] des membres assignables."""
        return []