import unittest

from app.runtime.governance.events import RuntimeEvent, RuntimeEventType
from app.storage import ConflictError
from app.storage.ports import EventStore
from app.storage.providers.memory import InMemoryEventStore


def event(event_id="event-1", execution_id="execution-1"):
    return RuntimeEvent(
        event_id=event_id, event_type=RuntimeEventType.GRAPH_STARTED,
        execution_id=execution_id, trace_id="trace", agent_id="agent",
        agent_version="1", artifact_id="artifact", artifact_hash="hash",
        backend_type="current", status="running",
    )


class EventStoreContractTest(unittest.TestCase):
    def test_provider_satisfies_port_and_is_append_only(self):
        store = InMemoryEventStore()
        self.assertIsInstance(store, EventStore)
        stored_event = event()
        store.append(stored_event)
        store.append(event("event-2", "execution-2"))

        self.assertEqual((stored_event,), store.query(execution_id="execution-1"))
        with self.assertRaises(ConflictError):
            store.append(event())
