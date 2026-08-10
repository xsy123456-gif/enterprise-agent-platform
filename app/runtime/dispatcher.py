"""Runtime-layer dispatch from orchestration context to GraphRuntime."""

from hashlib import sha256
import json

from app.compiler.backend import BackendArtifact
from app.runtime.contracts import AgentRuntimeState
from app.runtime.governance.adapters import RuntimeEventContext, RuntimeEventMapper
from app.runtime.ports import CurrentRuntimeAdapter
from app.runtime.selector import RuntimeSelector


class BackendArtifactResolver:
    """Read-only runtime artifact lookup boundary."""

    def __init__(self, artifacts=None):
        self._artifacts = dict(artifacts or {})

    def register(self, artifact):
        key = (artifact.agent_id, artifact.agent_version, artifact.backend_type)
        self._artifacts[key] = artifact
        return artifact

    def get(self, agent_id, version, backend_type="current"):
        try:
            return self._artifacts[(agent_id, version, backend_type)]
        except KeyError as error:
            raise KeyError(
                f"Runtime artifact not found: {agent_id}:{version}:{backend_type}"
            ) from error


class AgentRuntimeStateFactory:
    """Maps orchestration AgentContext to the backend-neutral state contract."""

    def create(self, context, agent_id, version):
        return AgentRuntimeState(
            task_id=context.task_id,
            trace_id=context.trace_id,
            tenant_id=context.tenant_id,
            agent_id=agent_id,
            agent_version=version,
            messages=list(context.messages),
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
                 event_bus=None, event_store=None, event_mapper=None):
        self.selector = selector
        self.artifact_resolver = artifact_resolver
        self.state_factory = state_factory or AgentRuntimeStateFactory()
        self.event_bus = event_bus
        self.event_store = event_store
        self.event_mapper = event_mapper or RuntimeEventMapper()

    def execute_step(self, context, agent_id, version):
        definition = context.agent_definition
        backend_type = self.selector.backend_type_for(
            agent_definition=definition
        )
        artifact = self.artifact_resolver.get(agent_id, version, backend_type)
        state = self.state_factory.create(context, agent_id, version)
        backend = self.selector.select(
            agent=agent_id,
            version=version,
            agent_definition=definition,
        )
        result = backend.execute(artifact, state)
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
    def from_runtime_engine(cls, runtime_engine, agent_registry):
        resolver = BackendArtifactResolver()
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
        selector = RuntimeSelector(
            {"current": CurrentRuntimeAdapter(runtime_engine)},
            default_backend="current",
        )
        return cls(selector, resolver)


class LegacyRuntimeFacade:
    """Test/integration boundary for pre-GraphRuntime callers only."""

    def __init__(self, runtime):
        self._runtime = runtime

    def execute_step(self, context, agent_id, version):
        return self._runtime.run(context, agent_id=agent_id, version=version)
