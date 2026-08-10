from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.storage.exceptions import ConflictError


@dataclass(frozen=True)
class ArtifactBinding:
    agent_id: str
    agent_version: str
    backend_type: str
    artifact_ref: str
    artifact_hash: str
    status: str = "active"
    bound_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def key(self):
        return self.agent_id, self.agent_version, self.backend_type


class InMemoryArtifactBindingRepository:
    """Explicit replaceable provider for active deployment pointers."""

    def __init__(self):
        self._bindings = {}

    def bind(self, binding):
        if not isinstance(binding, ArtifactBinding):
            raise TypeError("binding must be ArtifactBinding")
        self._bindings[binding.key] = binding
        return binding

    def get(self, agent_id, agent_version, backend_type):
        return self._bindings.get((agent_id, agent_version, backend_type))

    def list_for_agent(self, agent_id, agent_version=None):
        return tuple(
            binding for binding in self._bindings.values()
            if binding.agent_id == agent_id
            and (agent_version is None or binding.agent_version == agent_version)
        )
