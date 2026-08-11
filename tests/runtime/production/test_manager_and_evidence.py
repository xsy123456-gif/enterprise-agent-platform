from types import SimpleNamespace

import pytest

from app.artifacts.storage import InMemoryArtifactRepository
from app.runtime.execution import ExecutionManager, InMemoryExecutionStore
from app.runtime.governance.events import RuntimeEvent
from app.runtime.production import (
    AgentCapacityManager,
    AgentDeploymentManager,
    AgentDeploymentPolicy,
    AgentExecutionQuota,
    AgentHealthManager,
    AgentLifecycleManager,
    ArtifactBinding,
    ProductionRuntimeManager,
    QuotaUsage,
)
from app.runtime.trace import TraceAssembler
from app.storage.providers.memory import InMemoryEventStore, InMemoryTraceRepository


def control_plane(max_parallel=1, backend_probe=lambda _: True):
    repository = InMemoryArtifactRepository()
    artifact = SimpleNamespace(
        artifact_id="sales:1", artifact_hash="hash-1",
        agent_id="sales_agent", agent_version="1", backend_type="langgraph",
    )
    repository.save(artifact)
    lifecycle = AgentLifecycleManager()
    lifecycle.create("sales_agent")
    for state in ("registered", "validated", "active"):
        lifecycle.transition("sales_agent", state)
    deployments = AgentDeploymentManager(repository)
    deployments.deploy(AgentDeploymentPolicy(
        "sales_agent", ArtifactBinding("sales:1", "hash-1", "deploy-v1")
    ))
    capacity = AgentCapacityManager({
        "sales_agent": AgentExecutionQuota(
            "sales_agent", max_parallel, 30, 5, 1000, "runtime-policy-v1"
        )
    })
    health = AgentHealthManager(repository, backend_probe=backend_probe)
    return ProductionRuntimeManager(lifecycle, deployments, capacity, health), artifact


def test_production_preflight_returns_exact_replay_evidence():
    manager, _ = control_plane()
    permit = manager.prepare_new_execution(
        agent_id="sales_agent", execution_id="execution-1",
        routing_key="execution-1",
    )
    assert permit.artifact.artifact_hash == "hash-1"
    assert permit.artifact.deployment_version == "deploy-v1"
    assert permit.runtime_policy_version == "runtime-policy-v1"
    assert permit.quota_decision.allowed


def test_production_preflight_rejects_unhealthy_runtime_without_capacity_leak():
    manager, _ = control_plane(backend_probe=lambda _: False)
    with pytest.raises(RuntimeError, match="unavailable"):
        manager.prepare_new_execution(
            agent_id="sales_agent", execution_id="execution-1",
            routing_key="execution-1",
        )
    assert manager.capacity.active_count("sales_agent") == 0


def test_production_preflight_rejects_parallel_over_capacity():
    manager, _ = control_plane(max_parallel=1)
    manager.prepare_new_execution(
        agent_id="sales_agent", execution_id="execution-1",
        routing_key="execution-1",
    )
    with pytest.raises(RuntimeError, match="quota"):
        manager.prepare_new_execution(
            agent_id="sales_agent", execution_id="execution-2",
            routing_key="execution-2",
        )


def test_complete_execution_releases_capacity_even_on_usage_overage():
    manager, _ = control_plane()
    manager.prepare_new_execution(
        agent_id="sales_agent", execution_id="execution-1",
        routing_key="execution-1",
    )
    decision = manager.complete_execution(
        "sales_agent", "execution-1", QuotaUsage(token_usage=1001)
    )
    assert not decision.allowed
    assert manager.capacity.active_count("sales_agent") == 0


def test_suspended_agent_can_resume_only_with_original_artifact_hash():
    manager, artifact = control_plane()
    manager.lifecycle.transition("sales_agent", "suspended")
    assert manager.assert_resume_allowed(
        "sales_agent", artifact.artifact_id, artifact.artifact_hash
    ) is artifact
    with pytest.raises(ValueError, match="artifact identity"):
        manager.assert_resume_allowed("sales_agent", artifact.artifact_id, "changed")


def test_execution_record_persists_production_snapshot_and_emits_it():
    state = SimpleNamespace(
        task_id="execution-1", execution_id="execution-1", trace_id="trace-1",
        agent_id="sales_agent", agent_version="1", tenant_id="tenant",
        user_id="user", deployment_version="deploy-v1",
        runtime_policy_version="runtime-policy-v1",
        quota_snapshot={"decision": "allowed", "runtime_health": "healthy"},
    )
    artifact = SimpleNamespace(
        artifact_id="sales:1", artifact_hash="hash-1", backend_type="langgraph"
    )
    events = InMemoryEventStore()
    manager = ExecutionManager(InMemoryExecutionStore(), event_store=events)
    record = manager.create(state, artifact)
    restored = type(record).from_dict(record.to_dict())
    emitted, = events.query("execution-1")
    assert restored.deployment_version == "deploy-v1"
    assert restored.quota_snapshot == record.quota_snapshot
    assert emitted.deployment_version == "deploy-v1"
    assert emitted.quota_decision == "allowed"


def test_trace_preserves_production_identity_and_decisions():
    repository = InMemoryTraceRepository()
    event = RuntimeEvent(
        event_type="graph.started", execution_id="execution-1", trace_id="trace-1",
        agent_id="sales_agent", agent_version="1", artifact_id="sales:1",
        artifact_hash="hash-1", backend_type="langgraph", status="started",
        deployment_version="deploy-v1", quota_decision="allowed",
        runtime_health="healthy",
    )
    trace = TraceAssembler(repository).consume(event)
    assert trace.deployment_version == "deploy-v1"
    assert trace.artifact_hash == "hash-1"
    assert trace.quota_decision == "allowed"
    assert trace.runtime_health == "healthy"
