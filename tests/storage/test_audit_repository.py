import unittest

from app.storage import ConflictError
from app.storage.ports import AuditRepository
from app.storage.providers.memory import InMemoryAuditRepository


class AuditRepositoryContractTest(unittest.TestCase):
    def test_provider_is_immutable_and_isolates_caller_mutation(self):
        repository = InMemoryAuditRepository()
        self.assertIsInstance(repository, AuditRepository)
        record = {"audit_id": "audit-1", "execution_id": "e-1", "data": {"x": 1}}
        repository.write(record)
        record["data"]["x"] = 2

        self.assertEqual(1, repository.export()[0]["data"]["x"])
        self.assertEqual(1, len(repository.query(execution_id="e-1")))
        with self.assertRaises(ConflictError):
            repository.write({"audit_id": "audit-1"})
