"""Haystack ingestion adapter — implements KnowledgeIngestionPort.

This is the control-plane write path: SourceDocument -> chunk -> ACL metadata
-> dense+sparse embedding -> Qdrant write, with stable document identity and
idempotent re-ingestion.
"""

from haystack import Document

from app.knowledge.ingestion.versioning import stable_document_id
from app.knowledge.models.document import SourceDocument
from app.knowledge.ports.ingestion import KnowledgeIngestionPort

from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .indexing_pipeline import IndexingPipeline


class HaystackIngestionAdapter(KnowledgeIngestionPort):
    def __init__(
        self,
        config: HaystackKnowledgeConfig | None = None,
        store_manager: QdrantStoreManager | None = None,
        indexing: IndexingPipeline | None = None,
    ):
        self.config = config or HaystackKnowledgeConfig()
        self.store_manager = store_manager or QdrantStoreManager(self.config)
        self.indexing = indexing or IndexingPipeline(self.config, self.store_manager)

    async def ingest(self, document: SourceDocument) -> str:
        haystack_doc = self._to_haystack_document(document)
        self.indexing.run(haystack_doc)
        return haystack_doc.meta["document_id"]

    async def update(self, document: SourceDocument) -> str:
        document_id = stable_document_id(
            document.source_system, document.external_id
        )
        self._delete_document_chunks(document_id)
        return await self.ingest(document)

    async def delete(self, document_id: str, version: str | None = None) -> None:
        self._delete_document_chunks(document_id)

    async def reindex(self, document_id: str) -> str:
        raise NotImplementedError("reindex requires a document repository")

    async def set_acl(self, document_id: str, access_policy: dict) -> None:
        raise NotImplementedError("set_acl requires payload update support")

    def _to_haystack_document(self, document: SourceDocument) -> Document:
        document_id = stable_document_id(document.source_system, document.external_id)
        version = document.source_version or "unversioned"
        policy = dict(document.access_policy or {})

        def _first(value):
            if value is None:
                return None
            return value[0] if isinstance(value, (list, tuple)) else value

        meta = {
            "tenant_id": document.tenant_id,
            "store_id": _first(policy.get("store_id") or policy.get("allowed_stores")),
            "region": _first(policy.get("region") or policy.get("regions")),
            "department_id": _first(policy.get("department_id")),
            "security_level": policy.get("security_level", "public"),
            "knowledge_type": document.document_type,
            "document_id": document_id,
            "document_version": version,
            "source_system": document.source_system,
            "external_id": document.external_id,
            "source": policy.get("source_name") or document.title,
            "title": document.title,
            "language": document.language,
            "citation": {
                "source_id": policy.get("source_id") or document.identity,
                "source_type": document.document_type,
                "source_name": policy.get("source_name") or document.title,
                "document_id": document_id,
                "document_version": version,
                "page": policy.get("page"),
                "section": policy.get("section"),
            },
        }
        meta.update({k: v for k, v in (document.metadata or {}).items()})
        return Document(
            id=f"{document_id}:{version}", content=document.content, meta=meta
        )

    def _delete_document_chunks(self, document_id: str) -> None:
        documents = self.store_manager.store.filter_documents(
            {"field": "meta.document_id", "operator": "==", "value": document_id}
        )
        ids = [document.id for document in documents]
        if ids:
            self.store_manager.store.delete_documents(ids)

    def health(self):
        return self.store_manager.health()
