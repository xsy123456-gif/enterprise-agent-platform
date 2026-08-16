"""Enterprise Agent Registry (Phase 13.1).

A versioned, lifecycle-aware registry that makes Agents first-class platform
assets.  Identity is ``(agent_id, version)``; duplicate versions are rejected;
later versions never auto-activate — activation is explicit.
"""

from app.commerce.diagnostics.registry.base import VersionedRegistry
from app.platform.agent_control.domain import (
    AGENT_ACTIVE,
    AGENT_DEPRECATED,
    AGENT_DISABLED,
    AGENT_DRAFT,
    AGENT_VALIDATED,
)
from app.platform.agent_control.errors import AgentNotActiveError, AgentValidationError
from app.platform.agent_control.lifecycle import validate_artifact
from app.platform.agent_control.versioning import ensure_valid_checksum


class AgentRegistry(VersionedRegistry):
    """Versioned agents keyed by ``(agent_id, version)`` + lifecycle status."""

    def __init__(self):
        super().__init__("agent")
        self._status = {}

    def register(self, artifact):
        ensure_valid_checksum(artifact)
        super().register(artifact.agent_id, artifact.version, artifact)
        self._status[(artifact.agent_id, artifact.version)] = AGENT_DRAFT
        return artifact

    def validate(self, agent_id, version=None):
        version = self._resolve(agent_id, version)
        artifact = self.get(agent_id, version)
        validate_artifact(artifact)
        self._status[(agent_id, version)] = AGENT_VALIDATED
        return artifact

    def activate(self, agent_id, version=None):
        version = self._resolve(agent_id, version)
        if self._status[(agent_id, version)] != AGENT_VALIDATED:
            raise AgentValidationError(
                f"agent {agent_id!r}@{version} must be VALIDATED before activation"
            )
        self._status[(agent_id, version)] = AGENT_ACTIVE
        self._active[agent_id] = version
        return self._items[(agent_id, version)]

    def deprecate(self, agent_id, version=None):
        version = self._resolve(agent_id, version)
        self._status[(agent_id, version)] = AGENT_DEPRECATED

    def disable(self, agent_id, version=None):
        version = self._resolve(agent_id, version)
        self._status[(agent_id, version)] = AGENT_DISABLED

    def status(self, agent_id, version=None):
        version = self._resolve(agent_id, version)
        return self._status[(agent_id, version)]

    def get_active_artifact(self, agent_id):
        version = self._active.get(agent_id)
        if version is None:
            raise AgentNotActiveError(f"agent {agent_id!r} is not active")
        if self._status[(agent_id, version)] != AGENT_ACTIVE:
            raise AgentNotActiveError(
                f"agent {agent_id!r}@{version} is not ACTIVE "
                f"({self._status[(agent_id, version)]})"
            )
        return self._items[(agent_id, version)]

    def list_artifacts(self):
        return sorted(
            self._items.values(),
            key=lambda a: (a.agent_id, a.version),
        )

    def get(self, agent_id, version=None):
        return super().get(agent_id, version)

    def _resolve(self, agent_id, version):
        if version is not None:
            if (agent_id, version) not in self._items:
                from app.commerce.diagnostics.errors import UnknownDefinitionVersionError
                raise UnknownDefinitionVersionError(
                    f"agent {agent_id!r} has no version {version!r}"
                )
            return version
        active = self._active.get(agent_id)
        if active is not None:
            return active
        versions = self.versions(agent_id)
        if not versions:
            from app.commerce.diagnostics.errors import UnknownDefinitionError
            raise UnknownDefinitionError(f"agent {agent_id!r} is not registered")
        return versions[0]


__all__ = ["AgentRegistry"]
