import json
import unittest

from app.compiler.backend import BackendArtifact, CurrentBackendCompiler
from app.compiler.backend.langgraph import (
    LangGraphBackendArtifact, LangGraphBackendCompiler,
)
from app.compiler.models import (
    AgentGraphIR, EdgeIR, EdgeType, NodeIR, NodeType,
)


def graph():
    return AgentGraphIR(
        agent_id="sales_agent", version="1.0",
        nodes=(
            NodeIR("start", NodeType.START),
            NodeIR("governance", NodeType.GOVERNANCE),
            NodeIR("agent", NodeType.AGENT),
            NodeIR("tool:crm", NodeType.TOOL, bindings={"tool_name": "crm"}),
            NodeIR("end", NodeType.END),
        ),
        edges=(
            EdgeIR("start", "governance"),
            EdgeIR("governance", "agent"),
            EdgeIR(
                "agent", "tool:crm", "action.tool == 'crm'", EdgeType.CONDITIONAL,
            ),
            EdgeIR("tool:crm", "agent"),
            EdgeIR("agent", "end", "action == 'finish'", EdgeType.CONDITIONAL),
        ),
        state_schema={"messages": "list"}, bindings={},
        execution_policy={"max_steps": 10},
    )


class LangGraphBackendCompilerTest(unittest.TestCase):
    def test_ir_to_langgraph_artifact(self):
        artifact = LangGraphBackendCompiler().compile(graph())
        self.assertIsInstance(artifact, LangGraphBackendArtifact)
        self.assertEqual("langgraph", artifact.backend_type)
        self.assertEqual("langgraph.backend/v1", artifact.runtime_definition["schema_version"])
        adapters = {
            node["id"]: node["adapter"]
            for node in artifact.runtime_definition["nodes"]
        }
        self.assertEqual("AgentNodeAdapter", adapters["agent"])
        self.assertEqual("ToolNodeAdapter", adapters["tool:crm"])

    def test_artifact_hash_is_stable_and_backend_specific(self):
        first = LangGraphBackendCompiler().compile(graph())
        second = LangGraphBackendCompiler().compile(graph())
        current = CurrentBackendCompiler().compile(graph())
        self.assertEqual(first.artifact_hash, second.artifact_hash)
        self.assertEqual(first.graph_ir_hash, current.graph_ir_hash)
        self.assertNotEqual(first.artifact_hash, current.artifact_hash)

    def test_runtime_definition_serialization(self):
        artifact = LangGraphBackendCompiler().compile(graph())
        payload = json.loads(json.dumps(artifact.to_dict()))
        restored = BackendArtifact.from_dict(payload)
        self.assertEqual(artifact.to_dict(), restored.to_dict())
        self.assertNotIn("StateGraph", json.dumps(payload))
