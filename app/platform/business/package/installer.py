"""Package installer (Phase 16.1).

Installs a PUBLISHED package into a tenant: creates agents, skill bindings,
knowledge documents, workflow templates and records integration requirements.
Installation must pass tenant governance first.
"""

from dataclasses import dataclass, field

from app.platform.business.errors import EntitlementError
from app.platform.business.package.domain import PACKAGE_INSTALLED, AgentPackage


@dataclass(frozen=True)
class InstallResult:
    package_id: str
    version: str
    tenant_id: str
    created_agents: tuple[str, ...] = ()
    created_knowledge: tuple[str, ...] = ()
    workflow_templates: tuple[str, ...] = ()
    required_integrations: tuple[str, ...] = ()

    def __post_init__(self):
        for name in ("created_agents", "created_knowledge", "workflow_templates",
                     "required_integrations"):
            object.__setattr__(self, name, tuple(getattr(self, name) or ()))


class PackageInstaller:

    def __init__(self, governance=None, agent_registry=None,
                 knowledge_service=None):
        self.governance = governance
        self.agent_registry = agent_registry
        self.knowledge_service = knowledge_service
        self.installed = {}

    def install(self, package: AgentPackage, tenant_id: str) -> InstallResult:
        if package.status != PACKAGE_INSTALLED and package.status != "PUBLISHED":
            from app.platform.business.errors import PackageNotPublishedError
            raise PackageNotPublishedError(
                f"package {package.package_id!r} is {package.status!r}"
            )
        if self.governance is not None:
            allowed = self.governance.authorize_install(tenant_id, package)
            if not allowed:
                raise EntitlementError(
                    f"tenant {tenant_id!r} cannot install {package.package_id!r}"
                )

        created_agents = []
        if self.agent_registry is not None:
            for agent_id in package.agents:
                self.agent_registry.register(agent_id, tenant_id)
                created_agents.append(agent_id)

        created_knowledge = []
        if self.knowledge_service is not None:
            for doc in package.knowledge_bundle:
                self.knowledge_service.ingest(doc, tenant_id, "")
                created_knowledge.append(doc)

        result = InstallResult(
            package_id=package.package_id, version=package.version,
            tenant_id=tenant_id, created_agents=tuple(created_agents),
            created_knowledge=tuple(created_knowledge),
            workflow_templates=package.workflow_templates,
            required_integrations=package.required_integrations,
        )
        self.installed[(tenant_id, package.package_id, package.version)] = result
        return result


__all__ = ["PackageInstaller", "InstallResult"]
