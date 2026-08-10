import unittest

from app.runtime.contracts import (
    AgentRuntimeState, NodeContract, NodeResult, NodeType,
)


class _Node(NodeContract):
    def execute(self, state):
        return NodeResult("completed", {"current_node": "end"})


class NodeContractTest(unittest.TestCase):
    def test_node_contract_returns_state_patch(self):
        state = AgentRuntimeState(
            "task", "trace", "tenant", "agent", "1.0", current_node="agent",
        )
        result = _Node().execute(state)
        state.apply_patch(result.state_patch)
        self.assertEqual("end", state.current_node)
        self.assertEqual("SUBGRAPH", NodeType.SUBGRAPH.value)
