"""Versioned AgentRegistry with a lifecycle (Phase 12.1).

An Agent moves DRAFT -> VALIDATED -> ACTIVE (then DEPRECATED / DISABLED).
``register`` stores the role ``AgentDefinition`` plus its ``AgentManifest``
capability declaration; ``validate`` runs the lifecycle checks (skills +
capabilities); only ACTIVE agents may run.
"""

from app.commerce.agents.domain import (
    AGENT_ACTIVE,
    AGENT_DEPRECATED,
    AGENT_DISABLED,
    AGENT_DRAFT,
    AGENT_VALIDATED,
)
from app.commerce.agents.errors import AgentNotActiveError
from app.commerce.agents.lifecycle import validate_agent
from app.commerce.diagnostics.registry.base import VersionedRegistry


class AgentRegistry(VersionedRegistry):
    """Versioned agents keyed by ``(agent_id, version)`` + lifecycle status."""

    def __init__(self, skill_registry=None, known_capability_ids=None):
        super().__init__("agent")
        self.skill_registry = skill_registry
        self.known_capability_ids = known_capability_ids
        self._status = {}
        self._manifests = {}

    def register(self, definition, manifest=None):
        result = super().register(definition.agent_id, definition.version, definition)
        self._status[(definition.agent_id, definition.version)] = AGENT_DRAFT
        if manifest is not None:
            self._manifests[(definition.agent_id, definition.version)] = manifest
        return result

    def validate(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        definition = self.get(agent_id, version)
        manifest = self._manifests.get((agent_id, version))
        if manifest is None:
            from app.commerce.agents.errors import AgentValidationError
            raise AgentValidationError(
                f"agent {agent_id!r}@{version} has no manifest to validate"
            )
        validate_agent(definition, manifest, self.skill_registry,
                       self.known_capability_ids)
        self._status[(agent_id, version)] = AGENT_VALIDATED
        return definition

    def activate(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        if self._status[(agent_id, version)] != AGENT_VALIDATED:
            from app.commerce.agents.errors import AgentValidationError
            raise AgentValidationError(
                f"agent {agent_id!r}@{version} must be VALIDATED before activation"
            )
        self._status[(agent_id, version)] = AGENT_ACTIVE
        self._active[agent_id] = version
        return self._items[(agent_id, version)]

    def deprecate(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        self._status[(agent_id, version)] = AGENT_DEPRECATED

    def disable(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        self._status[(agent_id, version)] = AGENT_DISABLED

    def status(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        return self._status[(agent_id, version)]

    def manifest(self, agent_id, version=None):
        version = self._resolve_version(agent_id, version)
        return self._manifests.get((agent_id, version))

    def get_active_agent(self, agent_id):
        version = self._active.get(agent_id)
        if version is None:
            raise AgentNotActiveError(f"agent {agent_id!r} is not active")
        if self._status[(agent_id, version)] != AGENT_ACTIVE:
            raise AgentNotActiveError(
                f"agent {agent_id!r}@{version} is not ACTIVE "
                f"({self._status[(agent_id, version)]})"
            )
        return self._items[(agent_id, version)]

    def get(self, agent_id, version=None):
        return super().get(agent_id, version)

    def _resolve_version(self, agent_id, version):
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
