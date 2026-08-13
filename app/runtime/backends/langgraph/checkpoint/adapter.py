from langgraph.checkpoint.base import BaseCheckpointSaver

from .base import LangGraphCheckpointer


class CheckpointerAdapter(BaseCheckpointSaver, LangGraphCheckpointer):
    """Thin adapter for a LangGraph BaseCheckpointSaver implementation."""

    def __init__(self, saver):
        if saver is None:
            raise ValueError("saver is required")
        super().__init__()
        self.saver = saver

    def get(self, config):
        return self.saver.get(config)

    def get_tuple(self, config):
        return self.saver.get_tuple(config)

    def put(self, config, checkpoint, metadata, new_versions):
        return self.saver.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=""):
        return self.saver.put_writes(config, writes, task_id, task_path)

    def list(self, config, *, filter=None, before=None, limit=None):
        return self.saver.list(config, filter=filter, before=before, limit=limit)

    def __getattr__(self, name):
        # Preserve the complete LangGraph BaseCheckpointSaver surface while
        # keeping the platform-facing dependency at this adapter boundary.
        return getattr(self.saver, name)


def create_postgres_checkpointer(connection_string):
    """Create the optional postgres saver without importing it in core code."""
    from .postgres import PostgresCheckpointAdapter
    return PostgresCheckpointAdapter(connection_string)
