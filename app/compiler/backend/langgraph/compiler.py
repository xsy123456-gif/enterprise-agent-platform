from dataclasses import dataclass

from app.compiler.backend.base import BackendCompiler
from app.compiler.backend.langgraph.generator import LangGraphDefinitionGenerator
from app.compiler.backend.models import BackendArtifact


@dataclass(frozen=True)
class LangGraphBackendArtifact(BackendArtifact):
    """Typed marker for a serialized LangGraph backend artifact."""


class LangGraphBackendCompiler(BackendCompiler):
    backend_type = "langgraph"

    def __init__(self, generator=None, backend_version="1.2", compiler_version="v0.8.2"):
        self.generator = generator or LangGraphDefinitionGenerator()
        self.backend_version = backend_version
        self.compiler_version = compiler_version

    def compile(self, graph_ir, dependency_snapshot=None):
        runtime_definition = self.generator.generate(graph_ir)
        dependencies = {
            "graph_ir_schema": graph_ir.schema_version,
            "langgraph": ">=1.2,<2.0",
        }
        if dependency_snapshot:
            dependencies["snapshot"] = (
                dependency_snapshot.to_dict()
                if hasattr(dependency_snapshot, "to_dict")
                else dict(dependency_snapshot)
            )
        return LangGraphBackendArtifact.create(
            agent_id=graph_ir.agent_id,
            agent_version=graph_ir.version,
            backend_type=self.backend_type,
            backend_version=self.backend_version,
            compiler_version=self.compiler_version,
            graph_ir_hash=graph_ir.stable_hash(),
            runtime_definition=runtime_definition,
            dependencies=dependencies,
        )
