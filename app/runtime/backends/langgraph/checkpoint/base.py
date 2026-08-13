from abc import ABC, abstractmethod


class LangGraphCheckpointer(ABC):
    """Backend checkpoint boundary; implementations are injected at compile time."""

    @abstractmethod
    def get(self, config):
        raise NotImplementedError

    @abstractmethod
    def put(self, config, checkpoint, metadata, new_versions):
        raise NotImplementedError

    @abstractmethod
    def put_writes(self, config, writes, task_id, task_path=""):
        raise NotImplementedError

    @abstractmethod
    def list(self, config, *, filter=None, before=None, limit=None):
        raise NotImplementedError


def create_in_memory_checkpointer():
    """Use LangGraph's tested in-memory saver for development/testing."""
    from langgraph.checkpoint.memory import MemorySaver
    return MemorySaver()
