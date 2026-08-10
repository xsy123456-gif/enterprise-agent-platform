import unittest

from app.runtime.backends.langgraph.state_adapter import LangGraphStateAdapter
from app.runtime.contracts import AgentRuntimeState


class LangGraphStateAdapterTest(unittest.TestCase):
    def test_state_conversion_is_contract_preserving(self):
        state = AgentRuntimeState(
            "task", "trace", "tenant", "agent", "1.0",
            messages=[{"role": "user", "content": "hello"}],
            metadata={"user_id": "user"},
        )
        adapter = LangGraphStateAdapter()
        backend = adapter.to_backend(state)
        backend["_action"] = {"type": "finish"}
        restored = adapter.from_backend(backend)
        self.assertEqual(state.to_dict(), restored.to_dict())
        self.assertFalse(hasattr(restored, "_action"))
