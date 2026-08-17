"""Action executor port (Phase 16.3 / 18.3).

The runtime executes an action only after validate -> permission -> approval ->
execute -> audit.  The agent never has this surface — it only produces an
``ActionProposal``.

Phase 18.3: the *actual* external execution goes through ``ActionExecutionPort``
(which the Runtime Foundation fulfills), so the governance runtime never owns a
parallel execution path.
"""

from abc import ABC, abstractmethod


class ActionExecutor(ABC):
    @abstractmethod
    def execute(self, action, context=None):
        pass


class ActionExecutionPort(ABC):
    """The Runtime-boundary a governed action is dispatched through."""

    @abstractmethod
    def execute(self, action, context=None):
        pass


__all__ = ["ActionExecutor", "ActionExecutionPort"]
