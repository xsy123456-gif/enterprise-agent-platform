"""Document registry tests (in-memory + optional Postgres)."""

import os
import unittest

from app.knowledge.ingestion.registry import (
    DocumentRecord,
    InMemoryDocumentRegistry,
    PostgresDocumentRegistry,
)
from app.knowledge.models.document import SourceDocument


def _record(document_id="doc-1"):
    document = SourceDocument(
        source_system="cms", external_id="E1", tenant_id="tenant_A",
        document_type="policy", title="t", content="content",
        source_version="v1", access_policy={"security_level": "public"},
    )
    return DocumentRecord(
        document_id=document_id, source_system="cms", external_id="E1",
        tenant_id="tenant_A", source_version="v1", document=document,
        acl_version=2, index_version=3,
    )


class InMemoryRegistryTest(unittest.TestCase):
    def test_put_get_remove(self):
        registry = InMemoryDocumentRegistry()
        registry.put(_record())
        record = registry.get("doc-1")
        self.assertEqual(2, record.acl_version)
        self.assertEqual("content", record.document.content)
        registry.remove("doc-1")
        self.assertIsNone(registry.get("doc-1"))


@unittest.skipUnless(
    os.getenv("MEMORY_TEST_DATABASE_URL"), "MEMORY_TEST_DATABASE_URL not configured"
)
class PostgresRegistryTest(unittest.TestCase):
    def _registry(self):
        from app.infrastructure import PostgresProvider

        provider = PostgresProvider(os.environ["MEMORY_TEST_DATABASE_URL"])
        registry = PostgresDocumentRegistry(provider.connection_factory)
        registry.initialize_schema()
        return registry

    def test_durable_roundtrip(self):
        registry = self._registry()
        registry.put(_record("doc-pg-1"))
        # New instance simulates a restart.
        fresh = self._registry()
        record = fresh.get("doc-pg-1")
        self.assertIsNotNone(record)
        self.assertEqual("content", record.document.content)
        self.assertEqual(2, record.acl_version)
        fresh.remove("doc-pg-1")
        self.assertIsNone(fresh.get("doc-pg-1"))


if __name__ == "__main__":
    unittest.main()
