import json
import unittest

from app.runtime.contracts import AgentRuntimeState
from app.runtime.worker import WorkerInstance, WorkerStatus


class WorkerInstanceTest(unittest.TestCase):
    def state(self):
        return AgentRuntimeState("task-1", "trace-1", "tenant-1", "sales_agent", "1.0")

    def test_worker_instance_lifecycle_and_serialization(self):
        worker = WorkerInstance("sales_worker", "task-1", self.state())
        self.assertEqual(WorkerStatus.CREATED, worker.status)
        worker.start().complete()
        self.assertEqual(WorkerStatus.COMPLETED, worker.status)
        restored = WorkerInstance.from_dict(json.loads(json.dumps(worker.to_dict())))
        self.assertEqual(worker.to_dict(), restored.to_dict())

    def test_worker_failure_is_terminal(self):
        worker = WorkerInstance("sales_worker", "task-1", self.state())
        worker.start().fail()
        with self.assertRaisesRegex(ValueError, "Invalid Worker transition"):
            worker.start()
