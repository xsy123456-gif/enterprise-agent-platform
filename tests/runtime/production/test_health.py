from types import SimpleNamespace

import pytest

from app.artifacts.storage import InMemoryArtifactRepository
from app.runtime.production import (
    AgentHealthManager, AgentHealthStatus, ArtifactBinding,
)
from app.tools.registry import ToolRegistry


def dependencies():
    artifacts = InMemoryArtifactRepository()
    artifact = SimpleNamespace(
        artifact_id="sales:1", artifact_hash="hash-1",
        agent_id="sales_agent", agent_version="1",
    )
    artifacts.save(artifact)
    tools = ToolRegistry()
    tools.register("crm_query", object())
    return artifacts, tools, ArtifactBinding("sales:1", "hash-1", "1")


def test_healthy_deployment_checks_all_dependencies():
    artifacts, tools, binding = dependencies()
    manager = AgentHealthManager(
        artifacts, backend_probe=lambda _: True, tool_registry=tools,
        governance_probe=lambda _: True,
    )
    report = manager.check("sales_agent", binding, ["crm_query"])
    assert report.status is AgentHealthStatus.HEALTHY
    assert all(report.checks.values())


@pytest.mark.parametrize(
    ("variant", "reason"),
    [
        ("artifact", "artifact_missing_or_hash_mismatch"),
        ("backend", "backend_unavailable"),
        ("tool", "invalid_tool_binding:unknown"),
        ("governance", "governance_unavailable"),
    ],
)
def test_unhealthy_dependency_blocks_runtime(variant, reason):
    artifacts, tools, binding = dependencies()
    if variant == "artifact":
        binding = ArtifactBinding("sales:1", "wrong", "1")
    manager = AgentHealthManager(
        artifacts,
        backend_probe=(lambda _: variant != "backend"),
        tool_registry=tools,
        governance_probe=(lambda _: variant != "governance"),
    )
    required_tools = ["unknown"] if variant == "tool" else ["crm_query"]
    report = manager.check("sales_agent", binding, required_tools)
    assert report.status is AgentHealthStatus.UNAVAILABLE
    assert reason in report.reasons


def test_probe_exception_is_isolated_as_unavailable():
    artifacts, tools, binding = dependencies()

    def broken(_):
        raise ConnectionError("backend down")

    report = AgentHealthManager(
        artifacts, backend_probe=broken, tool_registry=tools
    ).check("sales_agent", binding, ["crm_query"])
    assert report.status is AgentHealthStatus.UNAVAILABLE


def test_noncritical_degradation_reports_warning():
    artifacts, tools, binding = dependencies()
    report = AgentHealthManager(
        artifacts, tool_registry=tools
    ).check("sales_agent", binding, ["crm_query"], warnings=["high_latency"])
    assert report.status is AgentHealthStatus.WARNING
    assert report.reasons == ("high_latency",)
