"""Phase 16.1 Vertical Agent Package tests."""

import pytest

from app.platform.business.errors import (
    PackageNotPublishedError,
    PackageValidationError,
    EntitlementError,
)
from app.platform.business.package import (
    AgentPackage,
    PackageInstaller,
    PackageRegistry,
)


def _package(**overrides):
    data = dict(
        package_id="commerce_operations_package", version="1.0",
        name="Commerce Operations", domain="commerce",
        agents=("commerce_operations_agent",),
        skills=("store_performance_diagnosis",),
        plans=("store_health_scan",),
        knowledge_bundle=("amazon_ops_handbook",),
        workflow_templates=("inventory_replenishment",),
        required_integrations=("amazon_sp_api",),
    )
    data.update(overrides)
    return AgentPackage(**data)


def test_package_checksum_stable():
    a = _package()
    b = _package()
    assert a.checksum == b.checksum
    c = _package(skills=("other",))
    assert c.checksum != a.checksum


def test_package_registry_lifecycle():
    registry = PackageRegistry()
    registry.register(_package())
    registry.validate("commerce_operations_package")
    registry.publish("commerce_operations_package")
    assert registry.get_published("commerce_operations_package").version == "1.0"


def test_package_requires_agents_to_validate():
    registry = PackageRegistry()
    registry.register(_package(agents=()))
    with pytest.raises(PackageValidationError):
        registry.validate("commerce_operations_package")


class _Governance:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def authorize_install(self, tenant_id, package):
        return self.allowed


class _AgentRegistry:
    def __init__(self):
        self.registered = []

    def register(self, agent_id, tenant_id):
        self.registered.append((agent_id, tenant_id))


def test_install_published_package():
    registry = PackageRegistry()
    package = _package()
    registry.register(package)
    registry.validate("commerce_operations_package")
    registry.publish("commerce_operations_package")
    agents = _AgentRegistry()
    installer = PackageInstaller(governance=_Governance(True), agent_registry=agents)
    result = installer.install(registry.get_published("commerce_operations_package"),
                               "company_A")
    assert result.created_agents == ("commerce_operations_agent",)
    assert result.required_integrations == ("amazon_sp_api",)
    assert agents.registered == [("commerce_operations_agent", "company_A")]


def test_install_not_published_raises():
    registry = PackageRegistry()
    registry.register(_package())
    installer = PackageInstaller(governance=_Governance(True))
    with pytest.raises(PackageNotPublishedError):
        installer.install(_package(), "company_A")


def test_install_governance_denied():
    registry = PackageRegistry()
    package = _package()
    registry.register(package)
    registry.validate("commerce_operations_package")
    registry.publish("commerce_operations_package")
    installer = PackageInstaller(governance=_Governance(False))
    with pytest.raises(EntitlementError):
        installer.install(registry.get_published("commerce_operations_package"),
                          "company_A")
