import os
import unittest

from app.composition import create_application
from app.infrastructure import PostgresProvider, RedisProvider, VectorStoreProvider
from app.runtime.backends.langgraph.checkpoint import create_in_memory_checkpointer


class ProductionFoundationTest(unittest.TestCase):
    def test_environment_containers_are_isolated(self):
        self.assertEqual("development", create_application("development").environment)
        self.assertEqual("testing", create_application("testing").environment)

    def test_production_wires_real_provider_boundaries(self):
        old = os.environ.get("MEMORY_DATABASE_URL")
        os.environ["MEMORY_DATABASE_URL"] = "postgresql://invalid/agentdb"
        try:
            container = create_application("production")
        finally:
            if old is None:
                os.environ.pop("MEMORY_DATABASE_URL", None)
            else:
                os.environ["MEMORY_DATABASE_URL"] = old
        self.assertIsInstance(container.infrastructure["database"], PostgresProvider)
        self.assertIsInstance(container.infrastructure["redis"], RedisProvider)
        self.assertIsInstance(container.infrastructure["vector"], VectorStoreProvider)

    def test_development_checkpoint_is_available(self):
        self.assertIsNotNone(create_in_memory_checkpointer())


if __name__ == "__main__":
    unittest.main()
