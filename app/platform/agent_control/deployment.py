"""Agent deployment model (Phase 13.3 / 18.10).

The same agent version can be deployed to multiple environments (DEV / TEST /
PRODUCTION).  Only an ACTIVE (published) agent may be deployed; deployment
status is tracked per (agent_id, environment).  Deployment state is durable
business state, so it is persisted behind an ``AgentDeploymentRepository`` port
(not a manager-internal dict).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.core.time import utc_now
from app.platform.agent_control.domain import (
    DEPLOYMENT_ACTIVE,
    DEPLOYMENT_DISABLED,
    DEPLOYMENT_STATUSES,
    ENVIRONMENTS,
)
from app.platform.agent_control.errors import DeploymentError


@dataclass(frozen=True)
class AgentDeployment:
    deployment_id: str
    agent_id: str
    agent_version: str
    environment: str
    status: str = DEPLOYMENT_ACTIVE
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.deployment_id:
            raise ValueError("deployment_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.environment not in ENVIRONMENTS:
            raise ValueError(f"unknown environment: {self.environment}")
        if self.status not in DEPLOYMENT_STATUSES:
            raise ValueError(f"unknown deployment status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "deployment_id": self.deployment_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "environment": self.environment,
            "status": self.status,
            "created_at": self.created_at,
        }


class AgentDeploymentRepository(ABC):
    """Storage boundary for deployment state (future Postgres adapter swaps in)."""

    @abstractmethod
    def put(self, agent_id, environment, deployment):
        pass

    @abstractmethod
    def get(self, agent_id, environment):
        pass

    @abstractmethod
    def list_in(self, environment):
        pass


class InMemoryAgentDeploymentRepository(AgentDeploymentRepository):

    def __init__(self):
        self._deployments = {}

    def put(self, agent_id, environment, deployment):
        self._deployments[(agent_id, environment)] = deployment
        return deployment

    def get(self, agent_id, environment):
        return self._deployments.get((agent_id, environment))

    def list_in(self, environment):
        return sorted(
            (d for d in self._deployments.values()
             if d.environment == environment),
            key=lambda d: d.agent_id,
        )


class DeploymentManager:

    def __init__(self, registry, repository=None):
        self.registry = registry
        self.repository = repository or InMemoryAgentDeploymentRepository()

    def deploy(self, agent_id, environment, version=None) -> AgentDeployment:
        if environment not in ENVIRONMENTS:
            raise DeploymentError(f"unknown environment: {environment}")
        artifact = self.registry.get_active_artifact(agent_id)
        resolved_version = version or artifact.version
        if version is not None and (agent_id, version) not in self.registry._items:
            raise DeploymentError(f"agent {agent_id!r}@{version} is not registered")
        deployment = AgentDeployment(
            deployment_id=f"{agent_id}:{environment}",
            agent_id=agent_id,
            agent_version=resolved_version,
            environment=environment,
        )
        return self.repository.put(agent_id, environment, deployment)

    def get(self, agent_id, environment):
        return self.repository.get(agent_id, environment)

    def disable(self, agent_id, environment):
        deployment = self.repository.get(agent_id, environment)
        if deployment is None:
            raise DeploymentError(
                f"no deployment for {agent_id!r} in {environment!r}"
            )
        disabled = AgentDeployment(
            deployment_id=deployment.deployment_id, agent_id=deployment.agent_id,
            agent_version=deployment.agent_version,
            environment=deployment.environment, status=DEPLOYMENT_DISABLED,
            created_at=deployment.created_at,
        )
        return self.repository.put(agent_id, environment, disabled)

    def active_in(self, environment):
        return [
            d for d in self.repository.list_in(environment)
            if d.status == DEPLOYMENT_ACTIVE
        ]


__all__ = [
    "AgentDeployment",
    "AgentDeploymentRepository",
    "InMemoryAgentDeploymentRepository",
    "DeploymentManager",
]
