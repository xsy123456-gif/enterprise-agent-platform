"""Optional native LangGraph PostgreSQL checkpointer boundary."""

from .adapter import CheckpointerAdapter


class PostgresCheckpointAdapter(CheckpointerAdapter):
    """Wrap ``PostgresSaver`` without leaking LangGraph into platform code."""

    def __init__(self, connection_string, saver=None):
        self.connection_string = connection_string
        if saver is None:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
            except ImportError as error:
                raise RuntimeError(
                    "Install langgraph-checkpoint-postgres for production durability"
                ) from error
            saver = PostgresSaver.from_conn_string(connection_string)
            # Depending on package version, from_conn_string returns either a
            # saver or a context manager.  Resolve the latter at the boundary.
            if hasattr(saver, "__enter__") and not hasattr(saver, "put"):
                saver = saver.__enter__()
        super().__init__(saver)

    def initialize_schema(self):
        setup = getattr(self.saver, "setup", None)
        if callable(setup):
            setup()
        return True

    def close(self):
        close = getattr(self.saver, "close", None)
        if callable(close):
            close()
