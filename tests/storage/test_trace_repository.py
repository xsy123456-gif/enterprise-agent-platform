import unittest

from app.runtime.governance.trace import ExecutionTrace
from app.storage import ConflictError, NotFoundError
from app.storage.ports import TraceRepository
from app.storage.providers.memory import InMemoryTraceRepository


def trace(trace_id="trace-1", execution_id="execution-1"):
    return ExecutionTrace(
        trace_id, execution_id, "agent", "artifact", "current",
        "completed", "root-span",
    )


class TraceRepositoryContractTest(unittest.TestCase):
    def test_provider_satisfies_port_and_is_append_only(self):
        repository = InMemoryTraceRepository()
        self.assertIsInstance(repository, TraceRepository)
        stored_trace = trace()
        repository.append(stored_trace)

        self.assertEqual("trace-1", repository.get("trace-1").trace_id)
        self.assertEqual((stored_trace,), repository.query("execution-1"))
        with self.assertRaises(ConflictError):
            repository.append(trace())
        with self.assertRaises(NotFoundError):
            repository.get("missing")
