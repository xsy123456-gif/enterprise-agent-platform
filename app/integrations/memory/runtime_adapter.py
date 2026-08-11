from app.memory.api.models import MemoryPrincipal
from app.memory.api.public_models import MemoryReadRequest
from app.memory.models.scope import MemoryScope


class RuntimeMemoryAdapter:
    """Translate Runtime state and Agent definition into Memory contracts."""

    def __init__(self, memory_system):
        self.memory_system = memory_system

    def retrieve(self, state, definition):
        if hasattr(state, "retrieved_memory_context"):
            return state.retrieved_memory_context
        tenant_id = getattr(state, "tenant_id", None)
        if not tenant_id:
            raise ValueError("Runtime state must provide tenant_id for Memory access")
        principal = MemoryPrincipal(
            subject_id=getattr(state, "subject_id", None) or state.user_id,
            tenant_id=tenant_id, user_id=state.user_id,
            agent_id=state.agent_name,
        )
        request = MemoryReadRequest(
            principal=principal,
            scope=MemoryScope(
                tenant_id=tenant_id, user_id=state.user_id,
                agent_id=state.agent_name,
                department_id=getattr(state, "department_id", None),
            ),
            query=state.task, types=list(getattr(definition, "memory_read", []) or []),
            trace_id=state.trace_id,
        )
        context = self.memory_system.read(request)
        state.retrieved_memory_context = context
        return context
