from app.runtime.checkpoint import CheckpointStore


class LangGraphCheckpointAdapter:
    """Bind backend execution to the platform CheckpointStore port."""

    def __init__(self, store: CheckpointStore):
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
