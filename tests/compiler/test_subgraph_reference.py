import unittest

from app.compiler.models import NodeIR, NodeType


class SubgraphReferenceTest(unittest.TestCase):
    def test_subgraph_reference_is_serializable(self):
        node = NodeIR(
            "sales_worker", NodeType.SUBGRAPH, subgraph_ref="sales_agent:1.0",
        )
        self.assertEqual(node, NodeIR.from_dict(node.to_dict()))

    def test_subgraph_node_requires_reference(self):
        with self.assertRaisesRegex(ValueError, "requires subgraph_ref"):
            NodeIR("sales_worker", NodeType.SUBGRAPH)
