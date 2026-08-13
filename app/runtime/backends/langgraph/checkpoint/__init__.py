from .adapter import CheckpointerAdapter, create_postgres_checkpointer
from .base import LangGraphCheckpointer, create_in_memory_checkpointer
from .postgres import PostgresCheckpointAdapter


class LangGraphCheckpointAdapter:
    """Persist the platform-neutral AgentRuntimeState alongside LangGraph."""

    def __init__(self, store):
        self.store = store

    @staticmethod
    def execution_id(state):
        return state.metadata.get("execution_id") or state.task_id

    def save(self, state):
        return self.store.save(self.execution_id(state), state)

    def load(self, execution_id):
        return self.store.load(execution_id)

    def delete(self, execution_id):
        return self.store.delete(execution_id)

__all__ = [
    "LangGraphCheckpointer", "LangGraphCheckpointAdapter", "CheckpointerAdapter", "create_in_memory_checkpointer",
    "create_postgres_checkpointer", "PostgresCheckpointAdapter",
]
