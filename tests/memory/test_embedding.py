import json
import math
import os
import unittest

from app.memory.api.models import MemoryPrincipal, MemoryRetrieveRequest
from app.memory.embedding.config import EmbeddingConfig
from app.memory.embedding.factory import create_embedding_service
from app.memory.embedding.models import EmbeddingResult, EmbeddingSpace
from app.memory.embedding.providers.ollama import OllamaEmbeddingProvider
from app.memory.embedding.service import EmbeddingDimensionError, EmbeddingService
from app.memory.models.item import MemoryItem
from app.memory.models.scope import MemoryScope
from app.memory.pipeline.read.fusion import MemoryCandidateFusion
from app.memory.pipeline.read.query_analyzer import MemoryQueryAnalyzer
from app.memory.pipeline.read.retriever import MemoryRetriever
from app.memory.pipeline.write.extractor import MemoryCandidate
from app.memory.pipeline.write.fine_dedup import MemoryFineDeduplicator


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StaticProvider:
    def __init__(self, vector):
        self.vector = vector
        self.space = EmbeddingSpace("static", "static", "1", len(vector))

    def embed(self, text):
        return EmbeddingResult(
            vector=self.vector, space=self.space,
        )


class CountingEmbeddingService:
    def __init__(self, vector):
        self.vector = vector
        self.calls = []
        self.space = EmbeddingSpace("counting", "counting", "1", len(vector))

    def embed(self, text):
        self.calls.append(text)
        return EmbeddingResult(
            vector=self.vector, space=self.space,
        )


class HybridRepository:
    def __init__(self, sql_candidates, vector_candidates):
        self.sql_candidates = sql_candidates
        self.vector_candidates = vector_candidates

    def search_sql(self, request, keywords):
        return self.sql_candidates

    def search_vector(self, request, embedding, embedding_space_id=None):
        return self.vector_candidates


def item(identifier):
    return MemoryItem(
        id=identifier, memory_key=f"customer:{identifier}:fact", type="customer",
        entity_id=identifier, attribute="fact",
        content=identifier, embedding=[1.0, 0.0], importance=0.8,
        embedding_space_id=EmbeddingSpace("test", "test", "1", 2).space_id,
        embedding_provider="test", embedding_model="test", embedding_version="1",
        embedding_dimension=2,
        confidence=0.9, source="test", tenant_id="tenant", department_id=None,
        user_id="user", agent_id="sales_agent",
    )


class EmbeddingLayerTest(unittest.TestCase):
    def test_ollama_provider_uses_external_http_response_metadata(self):
        captured = {}

        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeResponse({
                "model": "configured-model:release-1",
                "embeddings": [[0.1, 0.2, 0.3]],
            })

        provider = OllamaEmbeddingProvider(
            "http://embedding-host:11434", "configured-model",
            timeout=7, opener=opener,
        )
        result = provider.embed("customer fact")
        self.assertEqual("http://embedding-host:11434/api/embed", captured["url"])
        self.assertEqual(
            {"model": "configured-model", "input": "customer fact"},
            captured["body"],
        )
        self.assertEqual(3, result.dimension)
        self.assertEqual("configured-model", result.model)
        self.assertEqual("ollama", result.provider)
        self.assertEqual("release-1", result.version)

    def test_embedding_service_rejects_dimension_mismatch(self):
        service = EmbeddingService(StaticProvider([0.1, 0.2]), expected_dimension=3)
        with self.assertRaises(EmbeddingDimensionError):
            service.embed("fact")

    def test_fine_dedup_thresholds(self):
        existing = item("existing")
        judge_calls = []
        deduplicator = MemoryFineDeduplicator(
            judge=lambda candidate, current: judge_calls.append(candidate) or True
        )

        auto_merge = MemoryCandidate(
            "customer", "a", "fact", "same", "test",
            embedding=[0.95, math.sqrt(1 - 0.95 ** 2)],
            metadata={"embedding_space_id": existing.embedding_space_id},
        )
        judged_merge = MemoryCandidate(
            "customer", "a", "fact", "related", "test",
            embedding=[0.80, 0.60],
            metadata={"embedding_space_id": existing.embedding_space_id},
        )
        new_memory = MemoryCandidate(
            "customer", "a", "fact", "different", "test",
            embedding=[0.50, math.sqrt(1 - 0.50 ** 2)],
            metadata={"embedding_space_id": existing.embedding_space_id},
        )

        self.assertTrue(deduplicator.is_duplicate(auto_merge, existing))
        self.assertEqual([], judge_calls)
        self.assertTrue(deduplicator.is_duplicate(judged_merge, existing))
        self.assertEqual(1, len(judge_calls))
        self.assertFalse(deduplicator.is_duplicate(new_memory, existing))
        self.assertEqual(1, len(judge_calls))

    def test_fine_dedup_does_not_compare_different_spaces(self):
        existing = item("existing")
        candidate = MemoryCandidate(
            "customer", "a", "fact", "same", "test",
            embedding=[1.0, 0.0],
            metadata={"embedding_space_id": "different-space"},
        )
        deduplicator = MemoryFineDeduplicator(
            judge=lambda *_: self.fail("cross-space judge must not run")
        )
        self.assertFalse(deduplicator.is_duplicate(candidate, existing))

    def test_query_analyzer_routes_exact_and_semantic_queries(self):
        analyzer = MemoryQueryAnalyzer()
        exact = analyzer.analyze("合同编号10086")
        semantic = analyzer.analyze("客户A为什么选择产品B")
        self.assertFalse(exact.semantic_required)
        self.assertIn("10086", exact.keywords)
        self.assertTrue(semantic.semantic_required)

    def test_hybrid_retrieval_fuses_duplicate_candidates(self):
        shared = item("shared")
        semantic_only = item("semantic")
        embedding = CountingEmbeddingService([1.0, 0.0])
        retriever = MemoryRetriever(
            HybridRepository(
                [(shared, 1.0)], [(shared, 0.8), (semantic_only, 0.9)]
            ),
            MemoryQueryAnalyzer(), embedding, MemoryCandidateFusion(),
        )
        request = MemoryRetrieveRequest(
            principal=MemoryPrincipal("user", "tenant", "user", "sales_agent"),
            scope=MemoryScope("tenant", "user", "sales_agent"),
            query="客户A为什么选择产品B", trace_id="trace",
        )
        candidates = retriever.retrieve(request)
        self.assertEqual(2, len(candidates))
        self.assertEqual([request.query], embedding.calls)
        self.assertEqual({"shared", "semantic"}, {value[0].id for value in candidates})

    def test_exact_retrieval_does_not_call_embedding_provider(self):
        exact_item = item("contract-10086")
        embedding = CountingEmbeddingService([1.0, 0.0])
        retriever = MemoryRetriever(
            HybridRepository([(exact_item, 1.0)], []),
            MemoryQueryAnalyzer(), embedding, MemoryCandidateFusion(),
        )
        request = MemoryRetrieveRequest(
            principal=MemoryPrincipal("user", "tenant", "user", "sales_agent"),
            scope=MemoryScope("tenant", "user", "sales_agent"),
            query="合同编号10086", trace_id="trace",
        )
        self.assertEqual([exact_item.id], [item.id for item, _ in retriever.retrieve(request)])
        self.assertEqual([], embedding.calls)


@unittest.skipUnless(
    os.getenv("EMBEDDING_INTEGRATION_TEST", "").lower() == "true",
    "EMBEDDING_INTEGRATION_TEST is not enabled",
)
class OllamaEmbeddingIntegrationTest(unittest.TestCase):
    def test_configured_provider_returns_expected_dimension(self):
        dimension = int(os.environ["MEMORY_EMBEDDING_DIMENSION"])
        service = create_embedding_service(
            dimension, EmbeddingConfig.from_environment()
        )
        result = service.embed("企业客户合作风险")
        self.assertEqual(dimension, result.dimension)
        self.assertEqual(os.environ["EMBEDDING_MODEL"], result.model)


if __name__ == "__main__":
    unittest.main()
