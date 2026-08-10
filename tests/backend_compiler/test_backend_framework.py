import json
import unittest

from app.compiler.backend import (
    BackendArtifact, BackendCompilerRegistry, CurrentBackendCompiler,
)
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType


def graph():
    return AgentGraphIR(
        agent_id="sales_agent", version="1.0",
        nodes=(NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
        edges=(EdgeIR("start", "end"),), state_schema={}, bindings={},
    )


class BackendCompilerFrameworkTest(unittest.TestCase):
    def test_current_backend_compiles_serializable_artifact(self):
        artifact = CurrentBackendCompiler().compile(graph())
        payload = json.loads(json.dumps(artifact.to_dict()))
        self.assertEqual(artifact, BackendArtifact.from_dict(payload))
        self.assertEqual("current", artifact.backend_type)
        self.assertEqual(graph().stable_hash(), artifact.graph_ir_hash)

    def test_artifact_rejects_python_object_reference(self):
        with self.assertRaisesRegex(ValueError, "JSON serializable"):
            BackendArtifact.create(
                agent_id="agent", agent_version="1", backend_type="invalid",
                backend_version="1", compiler_version="1", graph_ir_hash="hash",
                runtime_definition={"callable": lambda: None},
            )

    def test_backend_compiler_registry_is_keyed_by_backend_type(self):
        registry = BackendCompilerRegistry()
        compiler = registry.register(CurrentBackendCompiler())
        self.assertIs(compiler, registry.get("current"))
        self.assertEqual(["current"], registry.list_backends())
        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(CurrentBackendCompiler())
