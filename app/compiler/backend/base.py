from abc import ABC, abstractmethod

from app.compiler.backend.models import BackendArtifact
from app.compiler.models import AgentGraphIR


class BackendCompiler(ABC):
    """Compile portable AgentGraphIR into one backend's serializable artifact."""

    backend_type: str

    @abstractmethod
    def compile(self, graph_ir: AgentGraphIR) -> BackendArtifact:
        pass
