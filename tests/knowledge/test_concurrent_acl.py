"""Concurrent ACL consistency test (real Qdrant).

Verifies that set_acl() concurrent with retrieve() never exposes a partial
ACL window: a public-clearance query must only ever see public chunks.
"""

import threading
import time
import unittest

from haystack import Document

from app.integrations.knowledge.haystack.config import HaystackKnowledgeConfig
from app.integrations.knowledge.haystack.document_store import QdrantStoreManager

COLLECTION = "knowledge_concurrent_acl"


def _qdrant_available():
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:6333/healthz", timeout=2):
            return True
    except Exception:
        return False


@unittest.skipUnless(_qdrant_available(), "Qdrant not reachable")
class ConcurrentAclTest(unittest.TestCase):
    def setUp(self):
        config = HaystackKnowledgeConfig(
            collection=COLLECTION, embedding_dim=8, use_sparse_embeddings=False
        )
        self.store_manager = QdrantStoreManager(config)
        store = self.store_manager.store
        store.write_documents([
            Document(
                id="chunk-1", content="public content",
                embedding=[0.1] * 8,
                meta={"document_id": "doc-1", "tenant_id": "tenant_A",
                      "security_level": "public", "knowledge_type": "policy"},
            ),
        ])

    def tearDown(self):
        try:
            self.store_manager.store.delete_documents(["chunk-1"])
        except Exception:
            pass

    def _public_query(self):
        docs = self.store_manager.store.filter_documents({
            "operator": "AND",
            "conditions": [
                {"field": "meta.tenant_id", "operator": "==", "value": "tenant_A"},
                {"field": "meta.security_level", "operator": "in", "value": ["public"]},
            ],
        })
        for doc in docs:
            # Invariant: a public query must never return a non-public chunk.
            if doc.meta.get("security_level") != "public":
                raise AssertionError(
                    f"ACL leak: public query returned {doc.meta.get('security_level')}"
                )
        return docs

    def test_no_partial_acl_window(self):
        stop = threading.Event()
        violations = []

        def toggle_acl():
            level = "confidential"
            while not stop.is_set():
                self.store_manager.set_acl_metadata("doc-1", {
                    "document_id": "doc-1", "tenant_id": "tenant_A",
                    "security_level": level, "knowledge_type": "policy",
                })
                level = "public" if level == "confidential" else "confidential"

        def query_loop():
            try:
                while not stop.is_set():
                    self._public_query()
            except AssertionError as error:
                violations.append(str(error))

        writer = threading.Thread(target=toggle_acl)
        reader = threading.Thread(target=query_loop)
        writer.start()
        reader.start()
        time.sleep(1.0)
        stop.set()
        writer.join()
        reader.join()

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
