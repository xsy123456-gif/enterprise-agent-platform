import unittest
from datetime import datetime, timezone

from app.runtime.contracts import RuntimeEvent, RuntimeEventType
from app.runtime.governance.adapters import RuntimeEventContext, RuntimeEventMapper
from app.runtime.governance.events import RuntimeEvent as GovernanceRuntimeEvent


class RuntimeEventMapperTest(unittest.TestCase):
    def context(self):
        return RuntimeEventContext(
            execution_id="execution", trace_id="trace", agent_id="agent",
            agent_version="1", artifact_id="artifact", artifact_hash="hash",
            backend_type="current", backend_metadata={"opaque": {"x": 1}},
        )

    def test_internal_event_maps_to_governance_contract(self):
        event = RuntimeEvent(
            RuntimeEventType.GRAPH_COMPLETED, "task",
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload={"result": "ok"},
        )
        mapped = RuntimeEventMapper().map(event, self.context())

        self.assertIsInstance(mapped, GovernanceRuntimeEvent)
        self.assertEqual("graph.completed", mapped.event_type)
        self.assertEqual("completed", mapped.status)
        self.assertEqual({"opaque": {"x": 1}, "legacy_event_type": "graph.completed"},
                         mapped.backend_metadata)

    def test_unknown_internal_event_is_not_guessed(self):
        event = RuntimeEvent(
            RuntimeEventType.WORKER_STARTED, "task",
        )
        self.assertEqual(
            "worker.started",
            RuntimeEventMapper().map(event, self.context()).event_type,
        )
