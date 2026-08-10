from app.runtime.governance.events import RuntimeEvent


class LangGraphResponseEventHook:
    """Emit canonical response evidence at the backend boundary, never Memory calls."""

    def __init__(self, event_bus=None, event_store=None):
        self.event_bus = event_bus
        self.event_store = event_store

    def emit(self, artifact, state, result):
        event = RuntimeEvent(
            event_type="response.completed",
            execution_id=state.execution_id or state.task_id,
            trace_id=state.trace_id,
            agent_id=state.agent_id,
            agent_version=state.agent_version,
            artifact_id=artifact.artifact_id,
            artifact_hash=artifact.artifact_hash,
            backend_type=artifact.backend_type,
            status="completed",
            payload={
                "tenant_id": state.tenant_id,
                "user_id": state.user_id,
                "department_id": state.department_id,
                "subject_id": state.request_context.get("subject_id"),
                "input": state.request_context.get("input") or state.metadata.get("task"),
                "output": result.response,
                "tool_results": list(result.state.tool_results),
                "permission_context": dict(state.permission_context),
                "policy_context": dict(state.policy_context),
                "metadata": {"task_id": state.task_id},
            },
        )
        if self.event_store is not None:
            self.event_store.append(event)
        if self.event_bus is not None:
            self.event_bus.publish(event)
        return event
