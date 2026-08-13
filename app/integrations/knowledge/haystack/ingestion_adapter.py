"""Haystack ingestion adapter — implements KnowledgeIngestionPort.

Control-plane write path: SourceDocument -> chunk -> ACL metadata -> dense +
sparse embedding -> Qdrant write, with stable identity, idempotent
re-ingestion, atomic set_acl, and reindex.
"""

from haystack import Document

from app.knowledge.errors import (
    KnowledgeAccessDeniedError,
    KnowledgeNotFoundError,
)
from app.knowledge.ingestion.registry import (
    DocumentRecord,
    InMemoryDocumentRegistry,
)
from app.knowledge.ingestion.versioning import stable_document_id
from app.knowledge.models.document import SourceDocument
from app.knowledge.ports.ingestion import KnowledgeIngestionPort

from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager
from .indexing_pipeline import IndexingPipeline


def _first(value):
    if value is None:
        return None
    return value[0] if isinstance(value, (list, tuple)) else value


class HaystackIngestionAdapter(KnowledgeIngestionPort):
    def __init__(
        self,
        config: HaystackKnowledgeConfig | None = None,
        store_manager: QdrantStoreManager | None = None,
        indexing: IndexingPipeline | None = None,
        registry: InMemoryDocumentRegistry | None = None,
    ):
        self.config = config or HaystackKnowledgeConfig()
        self.store_manager = store_manager or QdrantStoreManager(self.config)
        self.indexing = indexing or IndexingPipeline(self.config, self.store_manager)
        self.registry = registry or InMemoryDocumentRegistry()

    async def ingest(self, document: SourceDocument) -> str:
        haystack_doc = self._to_haystack_document(document)
        self.indexing.run(haystack_doc)
        self.registry.put(self._to_record(document))
        return haystack_doc.meta["document_id"]

    async def update(self, document: SourceDocument) -> str:
        document_id = stable_document_id(document.source_system, document.external_id)
        self.store_manager.delete_by_document_id(document_id)
        return await self.ingest(document)

    async def delete(self, document_id: str, version: str | None = None) -> None:
        self.store_manager.delete_by_document_id(document_id)
        self.registry.remove(document_id)

    async def reindex(self, document_id: str) -> str:
        record = self.registry.get(document_id)
        if record is None:
            raise KnowledgeNotFoundError(f"document not found: {document_id}")
        record.index_version += 1
        haystack_doc = self._to_haystack_document(
            record.document,
            acl_version=record.acl_version,
            index_version=record.index_version,
        )
        self.store_manager.delete_by_document_id(document_id)
        self.indexing.run(haystack_doc)
        self.registry.put(record)
        return document_id

    async def set_acl(self, document_id: str, access_policy: dict) -> None:
        record = self.registry.get(document_id)
        if record is None:
            raise KnowledgeNotFoundError(f"document not found: {document_id}")
        if self.store_manager.count_documents_by_document_id(document_id) == 0:
            raise KnowledgeNotFoundError(f"document has no chunks: {document_id}")
        record.acl_version += 1
        full_meta = self._build_meta(
            record.document, access_policy, record.acl_version, record.index_version
        )
        self.store_manager.set_acl_metadata(document_id, full_meta)
        record.access_policy = dict(access_policy)
        self.registry.put(record)

    def _to_record(self, document: SourceDocument) -> DocumentRecord:
        return DocumentRecord(
            document_id=stable_document_id(document.source_system, document.external_id),
            source_system=document.source_system,
            external_id=document.external_id,
            tenant_id=document.tenant_id,
            source_version=document.source_version or "unversioned",
            document=document,
            access_policy=dict(document.access_policy or {}),
        )

    def _to_haystack_document(
        self,
        document: SourceDocument,
        acl_version: int = 1,
        index_version: int = 1,
    ) -> Document:
        document_id = stable_document_id(document.source_system, document.external_id)
        version = document.source_version or "unversioned"
        meta = self._build_meta(document, document.access_policy, acl_version, index_version)
        return Document(
            id=f"{document_id}:{version}:{index_version}",
            content=document.content,
            meta=meta,
        )

    def _build_meta(
        self,
        document: SourceDocument,
        access_policy: dict,
        acl_version: int,
        index_version: int,
    ) -> dict:
        document_id = stable_document_id(document.source_system, document.external_id)
        version = document.source_version or "unversioned"
        policy = dict(access_policy or {})

        meta = {
            "tenant_id": document.tenant_id,
            "knowledge_type": document.document_type,
            "document_id": document_id,
            "document_version": version,
            "source_system": document.source_system,
            "external_id": document.external_id,
            "source": policy.get("source_name") or document.title,
            "title": document.title,
            "language": document.language,
            "acl_version": acl_version,
            "index_version": index_version,
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
        meta.update(self._acl_fields(document, policy, acl_version))
        meta.update({k: v for k, v in (document.metadata or {}).items()})
        return meta

    @staticmethod
    def _acl_fields(document: SourceDocument, access_policy: dict, acl_version: int) -> dict:
        policy = dict(access_policy or {})
        security_level = policy.get("security_level", "public")
        if security_level not in ("public", "internal", "confidential", "restricted"):
            raise KnowledgeAccessDeniedError(
                f"unknown security level: {security_level}"
            )
        return {
            "store_id": _first(policy.get("store_id") or policy.get("allowed_stores")),
            "region": _first(policy.get("region") or policy.get("regions")),
            "department_id": _first(policy.get("department_id")),
            "security_level": security_level,
            "acl_version": acl_version,
        }

    def health(self):
        return self.store_manager.health()
