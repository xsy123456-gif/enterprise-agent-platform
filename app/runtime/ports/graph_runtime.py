from abc import ABC, abstractmethod
from typing import Any


class GraphRuntime(ABC):
    """Runtime port for executing a compiled Agent graph.

    ``graph`` is intentionally an opaque compiled artifact or IR.  The port
    prevents callers from taking a dependency on a particular graph engine.
    """

    @abstractmethod
    def execute(self, graph: Any, input: Any):
        pass
