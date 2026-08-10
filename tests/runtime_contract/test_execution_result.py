import json
import unittest

from app.runtime.contracts import AgentRuntimeState, ExecutionResult


class ExecutionResultTest(unittest.TestCase):
    def test_execution_result_round_trips(self):
        state = AgentRuntimeState("task", "trace", "tenant", "agent", "1.0")
        result = ExecutionResult("task", "completed", "done", state)
        restored = ExecutionResult.from_dict(json.loads(json.dumps(result.to_dict())))
        self.assertEqual(result.to_dict(), restored.to_dict())
