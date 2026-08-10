import unittest

from app.compiler.models import AgentGraphIR, EdgeIR, EdgeType, NodeIR, NodeType


class GraphIRSchemaTest(unittest.TestCase):
    def test_ir_v1_carries_runtime_policies(self):
        graph = AgentGraphIR(
            agent_id="sales_agent", version="1.0",
            nodes=(
                NodeIR("start", NodeType.START),
                NodeIR(
                    "agent", NodeType.AGENT,
                    execution_policy={"timeout": 30},
                    governance={"policy_ref": "sales_policy"},
                    retry_policy={"max_attempts": 3},
                ),
            ),
            edges=(EdgeIR("start", "agent", edge_type=EdgeType.NORMAL),),
            state_schema={"messages": "list"}, bindings={},
            execution_policy={"max_steps": 10, "concurrency": 1},
        )
        self.assertEqual("1.0", graph.schema_version)
        self.assertEqual(30, graph.nodes[1].execution_policy["timeout"])
        self.assertEqual("NORMAL", graph.edges[0].to_dict()["edge_type"])

    def test_error_and_human_approval_edges_are_supported(self):
        self.assertEqual(
            EdgeType.ERROR, EdgeIR("tool", "retry", edge_type=EdgeType.ERROR).edge_type,
        )
        self.assertEqual(
            EdgeType.HUMAN_APPROVAL,
            EdgeIR("review", "approved", edge_type=EdgeType.HUMAN_APPROVAL).edge_type,
        )
