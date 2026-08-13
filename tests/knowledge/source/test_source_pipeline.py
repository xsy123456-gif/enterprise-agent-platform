"""Source -> ingestion -> retrieval full pipeline test (real Qdrant + Ollama).

Skipped when Qdrant is unreachable.
"""

import asyncio
from pathlib import Path

import pytest

from app.integrations.knowledge.haystack import (
    HaystackIngestionAdapter,
    HaystackKnowledgeConfig,
    HaystackRetrieverAdapter,
    QdrantStoreManager,
)
from app.knowledge import (
    KnowledgeAccessContext,
    KnowledgeConfig,
    KnowledgeRetrieveRequest,
    KnowledgeService,
)
from app.knowledge.ingestion.service import KnowledgeIngestionService
from app.knowledge.source.local import LocalFileSourceAdapter

ROOT = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "sources"
COLLECTION = "knowledge_source_pipeline"


def _qdrant_available():
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:6333/healthz", timeout=2):
            return True
    except Exception:
        return False


def _context(clearance, stores=("JP01",)):
    return KnowledgeAccessContext(
        tenant_id="demo", user_id="u1", role="sales",
        authorized_store_ids=stores, authorized_regions=("JP",),
        authorized_knowledge_scopes=(
            "product", "faq", "policy", "sop", "store_rule", "management",
        ),
        security_clearance=clearance,
    )


def _sources(items):
    return {item.citation.source_name for item in items}


@pytest.mark.skipif(not _qdrant_available(), reason="Qdrant not reachable")
class TestSourcePipeline:
    @pytest.fixture(autouse=True)
    def setup(self):
        config = HaystackKnowledgeConfig(
            collection=COLLECTION,
            ollama_endpoint="http://172.25.192.1:11434",
            ollama_model="bge-m3",
            embedding_dim=1024,
        )
        self.store_manager = QdrantStoreManager(config)
        self.ingestion = KnowledgeIngestionService(
            HaystackIngestionAdapter(config=config, store_manager=self.store_manager)
        )
        self.service = KnowledgeService(
            HaystackRetrieverAdapter(config=config, store_manager=self.store_manager),
            config=KnowledgeConfig(),
        )

    def test_source_to_retrieval(self):
        adapter = LocalFileSourceAdapter(str(ROOT))
        sources = adapter.list_documents()
        assert len(sources) == 6

        async def run():
            ingested = 0
            for source in sources:
                for document in adapter.read_parts(source.source_id):
                    await self.ingestion.ingest(document)
                    ingested += 1
            return ingested

        ingested = asyncio.run(run())
        assert ingested >= 6
        assert self.store_manager.store.count_documents() >= 6

        async def retrieve(query, clearance, stores=("JP01",)):
            result = await self.service.retrieve(
                KnowledgeRetrieveRequest(query=query),
                _context(clearance, stores),
            )
            return result

        # public 用户查商品说明书（public）命中
        r1 = asyncio.run(retrieve("充电器支持100V吗", "public"))
        assert "商品说明书.docx" in _sources(r1.items)

        # public 用户查管理层制度（confidential）不命中
        r2 = asyncio.run(retrieve("管理层薪酬和经营分析", "public"))
        assert "管理层经营制度.docx" not in _sources(r2.items)

        # public 用户查广告SOP（internal）不命中
        r3 = asyncio.run(retrieve("广告ACOS升高先查什么", "public"))
        assert "广告投放SOP.docx" not in _sources(r3.items)

        # internal 用户查广告SOP 命中
        r4 = asyncio.run(retrieve("广告ACOS升高先查什么", "internal"))
        assert "广告投放SOP.docx" in _sources(r4.items)

        # JP01 员工查 JP01 规则命中
        r5 = asyncio.run(retrieve("店铺库存盘点和交接规范", "internal", ("JP01",)))
        assert "JP01内部规则.pdf" in _sources(r5.items)

        # US01 员工查 JP01 规则不命中（store 隔离）
        r6 = asyncio.run(retrieve("店铺库存盘点和交接规范", "internal", ("US01",)))
        assert "JP01内部规则.pdf" not in _sources(r6.items)

        # confidential 用户查管理层制度命中
        r7 = asyncio.run(retrieve("管理层薪酬和经营分析", "confidential"))
        assert "管理层经营制度.docx" in _sources(r7.items)

    def test_citation_preserved(self):
        adapter = LocalFileSourceAdapter(str(ROOT))

        async def run():
            for source in adapter.list_documents():
                for document in adapter.read_parts(source.source_id):
                    await self.ingestion.ingest(document)
            result = await self.service.retrieve(
                KnowledgeRetrieveRequest(query="退货期限多少天"),
                _context("public"),
            )
            return result

        result = asyncio.run(run())
        pages = {item.citation.page for item in result.items if item.citation.page}
        sections = {item.citation.section for item in result.items if item.citation.section}
        assert pages or sections
