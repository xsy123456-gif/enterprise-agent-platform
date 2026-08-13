from .base import LangGraphCheckpointer


class CheckpointerAdapter(LangGraphCheckpointer):
    """Thin adapter for a LangGraph BaseCheckpointSaver implementation."""

    def __init__(self, saver):
        if saver is None:
            raise ValueError("saver is required")
        self.saver = saver

    def get(self, config):
        return self.saver.get(config)

    def put(self, config, checkpoint, metadata, new_versions):
        return self.saver.put(config, checkpoint, metadata, new_versions)

    def put_writes(self, config, writes, task_id, task_path=""):
        return self.saver.put_writes(config, writes, task_id, task_path)

    def list(self, config, *, filter=None, before=None, limit=None):
        return self.saver.list(config, filter=filter, before=before, limit=limit)


def create_postgres_checkpointer(connection_string):
    """Create the optional postgres saver without importing it in core code."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as error:
        raise RuntimeError(
            "Postgres LangGraph checkpointer requires langgraph-checkpoint-postgres"
        ) from error
    saver = PostgresSaver.from_conn_string(connection_string)
    return CheckpointerAdapter(saver)
