"""Action executor port (Phase 16.3).

The runtime executes an action only after validate -> permission -> approval ->
execute -> audit.  The agent never has this surface — it only produces an
``ActionProposal``.
"""

from abc import ABC, abstractmethod


class ActionExecutor(ABC):
    @abstractmethod
    def execute(self, action, context=None):
        pass


__all__ = ["ActionExecutor"]
