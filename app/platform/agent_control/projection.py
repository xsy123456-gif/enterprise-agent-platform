"""Agent deployment projection (Phase 18.4).

The Agent Control Plane Registry is the enterprise source of truth; the Runtime
Registry and the Commerce Employee Agent Registry are *projections*.  The
``AgentDeploymentProjector`` projects a deployed (ACTIVE) control-plane
``AgentArtifact`` into the application/runtime projection(s), and enforces
version+checksum consistency (fail-closed on ``DEPLOYMENT_VERSION_MISMATCH``).
"""

from dataclasses import dataclass, field

from app.commerce.domain.base import utc_now
from app.platform.agent_control.errors import DeploymentVersionMismatchError


@dataclass(frozen=True)
class DeploymentProjection:
    agent_id: str
    version: str
    checksum: str
    environment: str
    projected_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "version": self.version,
            "checksum": self.checksum,
            "environment": self.environment,
            "projected_at": self.projected_at,
        }


class AgentDeploymentProjector:
    """Projects control-plane artifacts into application projections."""

    def __init__(self, control_plane_registry, commerce_agent_registry=None):
        self.control_plane_registry = control_plane_registry
        self.commerce_agent_registry = commerce_agent_registry
        self.projections = {}

    def project(self, agent_id, environment, version=None):
        artifact = self.control_plane_registry.get_active_artifact(agent_id)
        if version is not None and version != artifact.version:
            raise DeploymentVersionMismatchError(
                f"agent {agent_id!r}: requested {version!r} != active "
                f"{artifact.version!r}"
            )
        if self.commerce_agent_registry is not None:
            self._project_into_commerce(artifact)
        projection = DeploymentProjection(
            agent_id=agent_id, version=artifact.version,
            checksum=artifact.checksum, environment=environment,
        )
        self.projections[(agent_id, environment)] = projection
        return projection

    def verify(self, agent_id, version, checksum):
        artifact = self.control_plane_registry.get(agent_id, version)
        if artifact.checksum != checksum:
            raise DeploymentVersionMismatchError(
                f"agent {agent_id!r}@{version}: checksum {checksum!r} does not "
                f"match control plane {artifact.checksum!r}"
            )
        return True

    def _project_into_commerce(self, artifact):
        from app.commerce.agents.domain import AgentDefinition
        from app.commerce.agents.manifest import AgentManifest

        manifest = getattr(artifact, "manifest", None)
        definition = AgentDefinition(
            agent_id=artifact.agent_id, version=artifact.version,
            name=artifact.agent_id,
            description=getattr(manifest, "description", "") or artifact.agent_id,
            domain=getattr(manifest, "department", "") or "",
            owner=getattr(manifest, "owner", "") or "",
        )
        commerce_manifest = AgentManifest(
            agent_id=artifact.agent_id, version=artifact.version,
            description=getattr(manifest, "description", "") or "",
            skills=artifact.skills,
            default_skill=artifact.skills[0] if artifact.skills else "",
            required_capabilities=artifact.capabilities,
        )
        self.commerce_agent_registry.register(definition, commerce_manifest)
        self.commerce_agent_registry.validate(artifact.agent_id, artifact.version)
        self.commerce_agent_registry.activate(artifact.agent_id, artifact.version)


__all__ = ["AgentDeploymentProjector", "DeploymentProjection"]
