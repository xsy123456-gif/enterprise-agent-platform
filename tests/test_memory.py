import unittest

from app.memory.service import MemoryService
from app.memory.storage import MemoryStorage


class MemoryServiceTest(unittest.TestCase):
    def setUp(self):
        self.memory = MemoryService(MemoryStorage())

    def test_legacy_memory_record_can_be_recalled(self):
        self.memory.save(
            "customer",
            "Tesla",
            {"industry": "新能源汽车", "interest": "产品B"},
        )

        records = self.memory.recall("customer", "Tesla")

        self.assertEqual(1, len(records))
        self.assertEqual("Tesla", records[0]["key"])

    def test_scoped_memory_isolated_by_user_agent_and_scope(self):
        self.memory.save(
            "user-1", "sales_agent", "customer", "sales", {"name": "Tesla"}
        )

        self.assertEqual(
            [{"name": "Tesla"}],
            [record["content"] for record in self.memory.retrieve(
                "user-1", "sales_agent", "sales", "customer"
            )],
        )
        self.assertEqual(
            [], self.memory.retrieve("user-2", "sales_agent", "sales", "customer")
        )


if __name__ == "__main__":
    unittest.main()
