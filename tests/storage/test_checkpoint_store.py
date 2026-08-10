import unittest

from app.storage import NotFoundError
from app.storage.ports import CheckpointStore
from app.storage.providers.memory import InMemoryCheckpointStore


class CheckpointStoreContractTest(unittest.TestCase):
    def test_provider_satisfies_port_and_owns_state(self):
        store = InMemoryCheckpointStore()
        self.assertIsInstance(store, CheckpointStore)
        state = {"messages": ["one"]}
        store.save("execution-1", state)
        state["messages"].append("two")

        loaded = store.load("execution-1")
        self.assertEqual({"messages": ["one"]}, loaded)
        loaded["messages"].append("external")
        self.assertEqual({"messages": ["one"]}, store.load("execution-1"))

        store.delete("execution-1")
        with self.assertRaises(NotFoundError):
            store.load("execution-1")
