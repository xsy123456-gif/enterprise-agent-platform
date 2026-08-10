import json
import unittest

from app.runtime.governance.events import RuntimeEvent, RuntimeEventType


class RuntimeEvidenceEventTest(unittest.TestCase):
    def test_event_creation_serialization_and_opaque_backend_metadata(self):
        metadata = {
            "langgraph_node": "agent_node",
            "checkpoint_id": "checkpoint-1",
            "unknown_future_value": {"nested": [1, 2, 3]},
        }
        event = RuntimeEvent(
            event_type=RuntimeEventType.NODE_COMPLETED,
            execution_id="execution-1", trace_id="trace-1",
            agent_id="sales_agent", agent_version="1.0",
            artifact_id="artifact-1", artifact_hash="hash-1",
            backend_type="langgraph", node_id="agent", status="completed",
            payload={"summary": "agent completed"}, backend_metadata=metadata,
        )

        restored = RuntimeEvent.from_dict(json.loads(json.dumps(event.to_dict())))

        self.assertEqual(event, restored)
        self.assertEqual(metadata, restored.backend_metadata)
        self.assertFalse(hasattr(restored, "langgraph_node"))

    def test_backend_metadata_must_remain_a_dict(self):
        with self.assertRaisesRegex(TypeError, "opaque dict"):
            RuntimeEvent(
                event_type=RuntimeEventType.GRAPH_STARTED,
                execution_id="e", trace_id="t", agent_id="a", agent_version="1",
                artifact_id="x", artifact_hash="h", backend_type="custom",
                status="running", backend_metadata="backend-specific",
            )
