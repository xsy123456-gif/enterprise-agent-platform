from app.compiler.backend.base import BackendCompiler
from app.compiler.backend.models import BackendArtifact


class CurrentBackendCompiler(BackendCompiler):
    """Compile IR into the serializable contract consumed by RuntimeEngine."""

    backend_type = "current"

    def __init__(self, backend_version="1", compiler_version="v0.8.2"):
        self.backend_version = backend_version
        self.compiler_version = compiler_version

    def compile(self, graph_ir, dependency_snapshot=None):
        dependencies = {"graph_ir_schema": graph_ir.schema_version}
        if dependency_snapshot:
            dependencies["snapshot"] = (
                dependency_snapshot.to_dict()
                if hasattr(dependency_snapshot, "to_dict")
                else dict(dependency_snapshot)
            )
        return BackendArtifact.create(
            agent_id=graph_ir.agent_id,
            agent_version=graph_ir.version,
            backend_type=self.backend_type,
            backend_version=self.backend_version,
            compiler_version=self.compiler_version,
            graph_ir_hash=graph_ir.stable_hash(),
            runtime_definition={
                "entrypoint": "RuntimeEngine",
                "agent_id": graph_ir.agent_id,
                "agent_version": graph_ir.version,
                "execution_policy": dict(graph_ir.execution_policy),
            },
            dependencies=dependencies,
        )
