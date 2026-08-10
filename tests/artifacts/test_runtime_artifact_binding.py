from types import SimpleNamespace

from app.compiler.backend.langgraph import LangGraphBackendCompiler
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType
from app.governance.adapters import InMemoryExecutionCheckpointStore
from app.runtime.dispatcher import BackendArtifactResolver
from app.runtime.execution import ExecutionManager, InMemoryExecutionStore


def graph(policy):
    return AgentGraphIR(
        "sales", "1", (NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
        (EdgeIR("start", "end"),), {}, {"policy": policy},
    )


def runtime_state():
    return SimpleNamespace(
        execution_id="exec-1", task_id="exec-1", trace_id="trace-1",
        agent_id="sales", agent_version="1", user_id="user",
        tenant_id="tenant",
    )


def test_active_binding_can_change_without_mutating_stored_artifacts():
    resolver = BackendArtifactResolver()
    artifact_a = LangGraphBackendCompiler().compile(graph("a"))
    artifact_b = LangGraphBackendCompiler().compile(graph("b"))
    resolver.register(artifact_a)
    assert resolver.get("sales", "1", "langgraph") == artifact_a
    resolver.bind(artifact_b)
    assert resolver.get("sales", "1", "langgraph") == artifact_b
    assert resolver.get_by_hash(artifact_a.artifact_hash) == artifact_a


def test_resume_uses_execution_artifact_not_new_active_binding():
    resolver = BackendArtifactResolver()
    artifact_a = resolver.register(LangGraphBackendCompiler().compile(graph("a")))
    manager = ExecutionManager(
        InMemoryExecutionStore(), InMemoryExecutionCheckpointStore(),
        artifact_resolver=resolver,
    )
    manager.create(runtime_state(), artifact_a)
    manager.transition("exec-1", "running")
    manager.transition("exec-1", "waiting_approval")
    manager.save_checkpoint("exec-1", {"status": "waiting"}, "approval")

    artifact_b = LangGraphBackendCompiler().compile(graph("b"))
    resolver.bind(artifact_b)
    seen = {}
    manager.resume(
        "exec-1", {"approved": True},
        lambda checkpoint, approval, artifact: seen.update(artifact=artifact) or "ok",
    )
    assert seen["artifact"].artifact_hash == artifact_a.artifact_hash
    assert seen["artifact"].artifact_hash != artifact_b.artifact_hash
