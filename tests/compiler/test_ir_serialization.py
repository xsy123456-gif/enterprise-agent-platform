import json
import unittest

from app.artifacts import CompiledAgentArtifact
from app.compiler.models import AgentGraphIR, EdgeIR, NodeIR, NodeType


class GraphIRSerializationTest(unittest.TestCase):
    def graph(self):
        return AgentGraphIR(
            agent_id="sales_agent", version="1.0",
            nodes=(NodeIR("start", NodeType.START), NodeIR("end", NodeType.END)),
            edges=(EdgeIR("start", "end"),),
            state_schema={"messages": "list"}, bindings={"agent": "sales_agent"},
            execution_policy={"timeout": 30, "max_steps": 10},
        )

    def test_ir_json_round_trip(self):
        graph = self.graph()
        restored = AgentGraphIR.from_dict(json.loads(json.dumps(graph.to_dict())))
        self.assertEqual(graph, restored)

    def test_ir_and_artifact_hash_are_stable(self):
        first = self.graph()
        second = AgentGraphIR.from_dict(first.to_dict())
        self.assertEqual(first.stable_hash(), second.stable_hash())
        self.assertEqual(
            CompiledAgentArtifact.from_ir(first, "v0.8.1").graph_hash,
            CompiledAgentArtifact.from_ir(second, "v0.8.1").graph_hash,
        )
