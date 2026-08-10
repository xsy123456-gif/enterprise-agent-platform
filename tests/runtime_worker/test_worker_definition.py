import json
import unittest

from app.runtime.worker import WorkerDefinition


class WorkerDefinitionTest(unittest.TestCase):
    def test_worker_binds_subgraph_reference(self):
        worker = WorkerDefinition(
            "sales_worker", "sales_agent:1.0", {"timeout": 30, "max_steps": 10},
        )
        restored = WorkerDefinition.from_dict(json.loads(json.dumps(worker.to_dict())))
        self.assertEqual(worker, restored)
        self.assertEqual("sales_agent:1.0", restored.subgraph_ref)
