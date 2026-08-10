import json
import unittest

from app.runtime.contracts import AgentRuntimeState


class AgentRuntimeStateTest(unittest.TestCase):
    def state(self):
        return AgentRuntimeState(
            task_id="task-1", trace_id="trace-1", tenant_id="tenant-1",
            agent_id="sales_agent", agent_version="0.2",
        )

    def test_state_is_json_serializable_and_round_trips(self):
        state = self.state()
        state.messages.append({"role": "user", "content": "hello"})
        payload = json.loads(json.dumps(state.to_dict()))
        restored = AgentRuntimeState.from_dict(payload)
        self.assertEqual(state.to_dict(), restored.to_dict())

    def test_state_patch_updates_only_contract_fields(self):
        state = self.state()
        state.apply_patch({"status": "running", "current_node": "agent"})
        self.assertEqual("running", state.status)
        self.assertEqual("agent", state.current_node)
        with self.assertRaisesRegex(ValueError, "Unknown runtime state fields"):
            state.apply_patch({"llm_client": object()})
