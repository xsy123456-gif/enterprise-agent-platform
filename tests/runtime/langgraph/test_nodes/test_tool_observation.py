import unittest

from app.runtime.backends.langgraph.nodes import ObservationNode, ToolNode


class RecordingValidator:
    def __init__(self):
        self.calls = []

    def validate(self, action, state):
        self.calls.append((action, state))


class RecordingToolRunner:
    def __init__(self):
        self.calls = []

    def run(self, action, state):
        self.calls.append((action, state))
        call_id = state.add_tool_call(action.tool, action.input)
        result = {"customer": action.input["customer"]}
        state.add_tool_result(call_id, result)
        return result


class ToolObservationNodeTest(unittest.TestCase):
    def test_tool_node_delegates_to_validator_and_tool_runner(self):
        runner, validator = RecordingToolRunner(), RecordingValidator()
        patch = ToolNode(runner, validator)({
            "agent_id": "agent",
            "metadata": {"user_id": "user", "role": "sales"},
            "messages": [], "tool_results": [],
            "_action": {
                "type": "tool", "tool": "crm_query",
                "input": {"customer": "A"},
            },
        })

        self.assertEqual(1, len(validator.calls))
        self.assertEqual(1, len(runner.calls))
        self.assertEqual({"customer": "A"}, patch["observation"])

    def test_tool_node_has_no_direct_tool_dependency(self):
        node = ToolNode(RecordingToolRunner())

        self.assertFalse(hasattr(node, "tool"))
        self.assertFalse(hasattr(node, "registry"))

    def test_observation_node_records_result_for_next_reasoning_step(self):
        patch = ObservationNode()({
            "observation": {"customer": "A"},
            "intermediate_results": {},
        })

        self.assertEqual(
            [{"customer": "A"}],
            patch["intermediate_results"]["observations"],
        )
        self.assertIsNone(patch["_action"])
