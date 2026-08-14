"""Lifecycle authorization port (governance consumer side)."""

from abc import ABC, abstractmethod


class LifecycleAuthorizationPort(ABC):
    @abstractmethod
    def authorize(self, principal, action, agent_id, version) -> bool:
        """Authorize a lifecycle action. ``principal`` exposes principal_id/source."""
        raise NotImplementedError


class _SystemPrincipal:
    """Default system principal for internal (bootstrap) lifecycle operations."""

    principal_id = "platform.bootstrap"
    source = "system"


SYSTEM_PRINCIPAL = _SystemPrincipal()
