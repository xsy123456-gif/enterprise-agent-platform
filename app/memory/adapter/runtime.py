from app.memory.api.models import MemoryRetrieveRequest


class RuntimeMemoryAdapter:
    def __init__(self, memory_service):
        self.memory_service = memory_service

    def retrieve(self, state, definition):
        if hasattr(state, "retrieved_memory_context"):
            return state.retrieved_memory_context
        request = MemoryRetrieveRequest(
            user_id=state.user_id, agent_id=state.agent_name,
            tenant_id=getattr(state, "tenant_id", None) or "default",
            department_id=getattr(state, "department_id", None),
            query=state.task, types=list(getattr(definition, "memory_read", []) or []),
            trace_id=state.trace_id,
        )
        context = self.memory_service.retrieve(request)
        state.retrieved_memory_context = context
        return context
