from abc import ABC, abstractmethod

from app.compiler.backend.models import BackendArtifact
from app.runtime.contracts import AgentRuntimeState, ExecutionResult


class GraphRuntime(ABC):
    """Runtime port for executing a compiled Agent graph.

    ``graph`` is intentionally an opaque compiled artifact or IR.  The port
    prevents callers from taking a dependency on a particular graph engine.
    """

    @abstractmethod
    def execute(
        self,
        artifact: BackendArtifact,
        state: AgentRuntimeState,
    ) -> ExecutionResult:
        pass
