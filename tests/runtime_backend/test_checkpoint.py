import unittest

from app.runtime.checkpoint import InMemoryCheckpointStore
from app.runtime.contracts import AgentRuntimeState


class CheckpointStoreTest(unittest.TestCase):
    def test_save_load_delete_uses_runtime_contract(self):
        store = InMemoryCheckpointStore()
        state = AgentRuntimeState("task", "trace", "tenant", "agent", "1.0")
        store.save("execution", state)
        state.status = "changed-after-save"
        self.assertEqual("created", store.load("execution").status)
        self.assertEqual("created", store.delete("execution").status)
        self.assertIsNone(store.load("execution"))
