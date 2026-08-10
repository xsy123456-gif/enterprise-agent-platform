import json
import unittest

from app.runtime.governance.trace import BackendSpan, ExecutionTrace, NodeSpan


class TraceModelsTest(unittest.TestCase):
    def test_execution_trace_and_node_span_round_trip(self):
        trace = ExecutionTrace(
            "trace-1", "execution-1", "agent", "artifact", "current",
            "running", "root-span",
        )
        node = NodeSpan(
            trace_id="trace-1", node_id="agent", node_type="AGENT",
            status="completed", input_summary="one user message",
            output_summary="assistant response generated", parent_span_id="root-span",
        )
        self.assertEqual(
            trace, ExecutionTrace.from_dict(json.loads(json.dumps(trace.to_dict())))
        )
        self.assertEqual(
            node, NodeSpan.from_dict(json.loads(json.dumps(node.to_dict())))
        )

    def test_backend_span_preserves_metadata_without_backend_model(self):
        span = BackendSpan("langgraph", {"checkpoint_id": "opaque"})
        self.assertEqual(span, BackendSpan.from_dict(span.to_dict()))
        self.assertEqual({"checkpoint_id": "opaque"}, span.backend_metadata)
