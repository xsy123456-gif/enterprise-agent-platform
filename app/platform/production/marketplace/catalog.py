"""Agent catalog (Phase 15.6)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentCatalogEntry:
    agent_id: str
    description: str = ""
    category: str = ""
    publisher: str = ""
    rating: float = 0.0
    install_count: int = 0

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if not (0.0 <= self.rating <= 5.0):
            raise ValueError("rating must be in [0, 5]")

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "description": self.description,
            "category": self.category,
            "publisher": self.publisher,
            "rating": self.rating,
            "install_count": self.install_count,
        }


class AgentCatalog:

    def __init__(self):
        self._entries = {}

    def add(self, entry: AgentCatalogEntry):
        self._entries[entry.agent_id] = entry
        return entry

    def get(self, agent_id):
        return self._entries.get(agent_id)

    def list(self):
        return sorted(self._entries.values(), key=lambda e: e.agent_id)

    def install(self, agent_id, tenant_id):
        entry = self._entries[agent_id]
        installed = AgentCatalogEntry(
            agent_id=entry.agent_id, description=entry.description,
            category=entry.category, publisher=entry.publisher,
            rating=entry.rating, install_count=entry.install_count + 1,
        )
        self._entries[agent_id] = installed
        return installed


__all__ = ["AgentCatalogEntry", "AgentCatalog"]
