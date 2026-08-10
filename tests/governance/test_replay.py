import inspect
import json
import unittest

from app.runtime.governance.replay import (
    BackendComparison,
    ReplayRecord,
    ReplayService,
)


class ReplayContractTest(unittest.TestCase):
    def test_replay_record_creation_and_serialization(self):
        record = ReplayRecord(
            execution_id="execution-1",
            artifact_hash="sha256:artifact",
            initial_state_ref="checkpoint://initial",
            event_stream_ref="events://execution-1",
            checkpoint_refs=("checkpoint://one", "checkpoint://two"),
        )

        restored = ReplayRecord.from_dict(json.loads(json.dumps(record.to_dict())))

        self.assertEqual(record, restored)
        self.assertTrue(record.record_id)

    def test_backend_comparison_model(self):
        comparison = BackendComparison(
            execution_id="execution-1",
            backend_a="current",
            backend_b="langgraph",
            trace_diff={"node_order": ["agent", "tool"]},
            result_diff={"equivalent": True},
        )

        self.assertEqual(
            comparison,
            BackendComparison.from_dict(
                json.loads(json.dumps(comparison.to_dict()))
            ),
        )

    def test_replay_service_is_an_interface_only(self):
        self.assertTrue(inspect.isabstract(ReplayService))
        with self.assertRaises(TypeError):
            ReplayService()
