"""Runtime-layer dispatch from orchestration context to GraphRuntime."""

from hashlib import sha256
import json

from app.compiler.backend import BackendArtifact
from app.artifacts import (
    ArtifactBinding, ArtifactDependencySnapshot,
    InMemoryArtifactBindingRepository, InMemoryArtifactRepository,
)
from app.compiler import GraphCompiler
from app.compiler.backend.langgraph import LangGraphBackendCompiler
from app.runtime.backends.langgraph import (
    LangGraphNodeAdapterRegistry,
    LangGraphResponseEventHook,
    LangGraphRuntimeAdapter,
)
from app.runtime.contracts import AgentRuntimeState
from app.runtime.context_builder import AgentContextBuilder
from app.runtime.execution import ExecutionManager, PostgresExecutionStore
from app.governance.adapters.checkpoint import PersistentCheckpointStore
from app.runtime.governance.adapters import RuntimeEventContext, RuntimeEventMapper
from app.runtime.ports import CurrentRuntimeAdapter
from app.runtime.selector import RuntimeSelector
from app.runtime.governance.gate import GovernanceGate


class BackendArtifactResolver:
    """Read-only runtime artifact lookup boundary."""

    def __init__(self, artifacts=None, artifact_repository=None,
                 binding_repository=None):
        self.artifact_repository = (
            artifact_repository or InMemoryArtifactRepository()
        )
        self.binding_repository = (
            binding_repository or InMemoryArtifactBindingRepository()
        )
        for artifact in dict(artifacts or {}).values():
            self.register(artifact)

    def register(self, artifact):
        self.artifact_repository.save(artifact)
        self.binding_repository.bind(ArtifactBinding(
            agent_id=artifact.agent_id,
            agent_version=artifact.agent_version,
            backend_type=artifact.backend_type,
            artifact_ref=artifact.artifact_id,
            artifact_hash=artifact.artifact_hash,
        ))
        return artifact

    def get(self, agent_id, version, backend_type="current"):
        binding = self.binding_repository.get(agent_id, version, backend_type)
        artifact = (
            self.artifact_repository.get(binding.artifact_ref)
            if binding is not None else None
        )
        if artifact is None:
            raise KeyError(
                f"Runtime artifact not found: {agent_id}:{version}:{backend_type}"
            )
        if artifact.artifact_hash != binding.artifact_hash:
            raise ValueError("Artifact binding hash mismatch")
        return artifact

    def get_by_hash(self, artifact_hash):
        artifact = self.artifact_repository.get_by_hash(artifact_hash)
        if artifact is None:
            raise KeyError(f"Runtime artifact hash not found: {artifact_hash}")
        return artifact

    def bind(self, artifact):
        return self.register(artifact)


class AgentRuntimeStateFactory:
    """Maps orchestration AgentContext to the backend-neutral state contract."""

    def __init__(self, context_builder=None):
        self.context_builder = context_builder

    def create(self, context, agent_id, version):
        definition = context.agent_definition
        messages = (
            self.context_builder.build_messages(context, definition)
            if self.context_builder is not None
            else list(context.messages)
        )
        return AgentRuntimeState(
            task_id=context.task_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            agent_id=agent_id,
            agent_version=version,
            messages=messages,
            memory_context=context.memory_context,
            tool_results=list(context.tool_results),
            metadata={
                "task": context.task,
                "user_id": context.user_id,
                "role": context.role,
                "step_id": context.step_id,
                "capability": context.capability,
                "goal": context.goal,
                "department_id": context.department_id,
                "allowed_tools": list(
                    getattr(definition, "allowed_tools", []) or []
                ),
            },
            execution_id=context.task_id,
            user_id=context.user_id,
            department_id=context.department_id,
            permission_context={"role": context.role},
            request_context={"input": context.task},
            memory_policy=getattr(context.agent_definition, "memory_policy", None),
        )


class RuntimeDispatcher:
    """Thin runtime facade; execution remains inside a GraphRuntime backend."""

    def __init__(self, selector, artifact_resolver, state_factory=None,
                 event_bus=None, event_store=None, event_mapper=None,
                 execution_manager=None, agent_registry=None,
                 runtime_engine=None):
        self.selector = selector
        self.artifact_resolver = artifact_resolver
        self.state_factory = state_factory or AgentRuntimeStateFactory()
        self.event_bus = event_bus
        self.event_store = event_store
        self.event_mapper = event_mapper or RuntimeEventMapper()
        self.execution_manager = execution_manager
        self.agent_registry = agent_registry
        self.runtime_engine = runtime_engine

    def health(self):
        return True

    def execute_step(self, context, agent_id, version):
        definition = context.agent_definition
        backend_type = self.selector.backend_type_for(
            agent_definition=definition
        )
        artifact = self.artifact_resolver.get(agent_id, version, backend_type)
        state = self.state_factory.create(context, agent_id, version)
        state.metadata["artifact_id"] = artifact.artifact_id
        state.metadata["artifact_hash"] = artifact.artifact_hash
        state.metadata["backend_type"] = artifact.backend_type
        execution_record = (
            self.execution_manager.create(state, artifact)
            if self.execution_manager is not None else None
        )
        backend = self.selector.select(
            agent=agent_id,
            version=version,
            agent_definition=definition,
        )
        if (
            artifact.backend_type == "langgraph"
            and hasattr(backend, "response_event_hook")
        ):
            backend.response_event_hook = LangGraphResponseEventHook(
                self.event_bus, self.event_store
            )
        if execution_record is not None:
            self.execution_manager.transition(
                execution_record.execution_id, "running", state.current_node
            )
        try:
            result = backend.execute(artifact, state)
        except Exception:
            if execution_record is not None:
                self.execution_manager.transition(
                    execution_record.execution_id, "failed", state.current_node
                )
            raise
        if execution_record is not None:
            self.execution_manager.transition(
                execution_record.execution_id,
                "completed" if result.status == "completed" else "failed",
                result.state.current_node,
            )
        self._publish_governance_events(result.events, state, artifact)
        return result

    def _publish_governance_events(self, events, state, artifact):
        context = RuntimeEventContext(
            execution_id=state.task_id,
            trace_id=state.trace_id,
            agent_id=state.agent_id,
            agent_version=state.agent_version,
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.artifact_hash,
            backend_type=artifact.backend_type,
            worker_id=state.metadata.get("worker_id"),
        )
        for event in events:
            mapped = self.event_mapper.map(event, context)
            if mapped is None:
                continue
            if self.event_store is not None:
                self.event_store.append(mapped)
            if self.event_bus is not None:
                self.event_bus.publish(mapped)

    @classmethod
    def from_runtime_engine(cls, runtime_engine, agent_registry,
                            governance_gate=None, event_bus=None):
        resolver = BackendArtifactResolver()
        graph_compiler = GraphCompiler(compiler_version="v0.8.6")
        langgraph_compiler = LangGraphBackendCompiler(
            compiler_version="v0.8.6"
        )
        for agent in agent_registry.list_agents():
            definition = agent.definition or getattr(agent.instance, "definition", None)
            runtime = getattr(definition, "runtime", {}) if definition else {}
            payload = {
                "agent_id": agent.agent_id,
                "agent_version": agent.version,
                "capabilities": list(agent.capabilities),
                "runtime": dict(runtime or {}),
            }
            graph_hash = sha256(
                json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            resolver.register(BackendArtifact.create(
                agent_id=agent.agent_id,
                agent_version=agent.version,
                backend_type="current",
                backend_version="1",
                compiler_version="v0.8.4",
                graph_ir_hash=graph_hash,
                runtime_definition={
                    "entrypoint": "RuntimeEngine",
                    "agent_id": agent.agent_id,
                    "agent_version": agent.version,
                    "execution_policy": dict(runtime or {}).get(
                        "execution_policy", {}
                    ),
                },
            ))
            graph_ir = graph_compiler.compile(
                definition,
                agent_registry.capability_catalog,
                runtime_engine.tool_runner.registry,
                agent_registry,
            )
            snapshot = cls._dependency_snapshot(definition, agent_registry)
            langgraph_artifact = langgraph_compiler.compile(
                graph_ir, dependency_snapshot=snapshot.to_dict()
            )
            resolver.register(langgraph_artifact)
            agent_registry.attach_artifact(
                agent.agent_id, agent.version, langgraph_artifact.artifact_id
            )
        langgraph = LangGraphRuntimeAdapter(
            LangGraphNodeAdapterRegistry(
                agent_registry=agent_registry,
                tool_runner=runtime_engine.tool_runner,
                memory_adapter=runtime_engine.memory_adapter,
                governance_gate=governance_gate or GovernanceGate(
                    event_bus=event_bus
                ),
            )
        )
        selector = RuntimeSelector(
            {
                "langgraph": langgraph,
                "current": CurrentRuntimeAdapter(runtime_engine),
            },
            default_backend="langgraph",
        )
        execution_manager = None
        memory_adapter = getattr(runtime_engine, "memory_adapter", None)
        memory_system = getattr(memory_adapter, "memory_system", None)
        memory_runtime = getattr(memory_system, "runtime", None)
        connection_factory = getattr(memory_runtime, "connection_factory", None)
        if connection_factory is not None:
            execution_store = PostgresExecutionStore(connection_factory)
            checkpoint_store = PersistentCheckpointStore(connection_factory)
            execution_store.initialize_schema()
            checkpoint_store.initialize_schema()
            execution_manager = ExecutionManager(
                execution_store, checkpoint_store=checkpoint_store,
                artifact_resolver=resolver,
            )
        return cls(
            selector,
            resolver,
            state_factory=AgentRuntimeStateFactory(
                AgentContextBuilder(runtime_engine.memory_adapter)
            ),
            execution_manager=execution_manager,
            agent_registry=agent_registry,
            runtime_engine=runtime_engine,
        )

    @staticmethod
    def _dependency_snapshot(definition, agent_registry):
        prompt_hash = sha256(definition.system_prompt.encode("utf-8")).hexdigest()
        bindings = []
        for capability in definition.capabilities:
            for binding in agent_registry.get_tool_bindings(capability):
                bindings.append({
                    "tool_id": binding.tool_name,
                    "version": "unversioned",
                    "permission": binding.required_permission,
                    "capability": capability,
                })
        model = definition.runtime.get("model")
        return ArtifactDependencySnapshot(
            prompt_refs=({"ref": f"{definition.agent_id}/system", "hash": prompt_hash},),
            tool_bindings=tuple(bindings),
            policy_refs=(
                ({"policy_id": definition.policy_ref, "version": "unversioned"},)
                if definition.policy_ref else ()
            ),
            capabilities=tuple(definition.capabilities),
            model_binding={"model": model, "config_version": "manifest"} if model else {},
            memory_policy_ref=definition.memory_policy,
            governance_refs=(
                ({"policy_ref": definition.policy_ref},)
                if definition.policy_ref else ()
            ),
        )
