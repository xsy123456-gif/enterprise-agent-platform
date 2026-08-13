"""Optional native LangGraph PostgreSQL checkpointer boundary."""

from contextlib import ExitStack

from .adapter import CheckpointerAdapter


class PostgresCheckpointAdapter(CheckpointerAdapter):
    """Wrap ``PostgresSaver`` without leaking LangGraph into platform code."""

    def __init__(self, connection_string, saver=None):
        self.connection_string = connection_string
        self._stack = None
        if saver is None:
            try:
                from langgraph.checkpoint.postgres import PostgresSaver
            except ImportError as error:
                raise RuntimeError(
                    "Install langgraph-checkpoint-postgres for production durability"
                ) from error
            resource = PostgresSaver.from_conn_string(connection_string)
            # Keep the context manager alive for the adapter lifetime; entering
            # and immediately dropping it closes the underlying PostgreSQL
            # connection before the first checkpoint operation.
            if hasattr(resource, "__enter__") and not hasattr(resource, "put"):
                self._stack = ExitStack()
                saver = self._stack.enter_context(resource)
            else:
                saver = resource
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
        if self._stack is not None:
            self._stack.close()
            self._stack = None
