import json
import unittest

from app.runtime.contracts import AgentRuntimeState
from app.runtime.worker import WorkerContext, WorkerDefinition


class WorkerContextTest(unittest.TestCase):
    def test_context_binds_runtime_state_and_static_definition(self):
        context = WorkerContext(
            AgentRuntimeState(
                "task-1", "trace-1", "tenant-1", "sales_agent", "1.0",
            ),
            WorkerDefinition("sales_worker", "sales_agent:1.0"),
            {"requested_by": "supervisor"},
        )
        restored = WorkerContext.from_dict(json.loads(json.dumps(context.to_dict())))
        self.assertEqual(context.to_dict(), restored.to_dict())
        self.assertEqual("sales_agent:1.0", restored.worker_definition.subgraph_ref)
