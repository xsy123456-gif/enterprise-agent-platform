"""Knowledge ingestion service (Phase 15.5).

Ingest -> checksum -> version -> activate -> (governed) retrieval.  The service
stores document metadata (with a content checksum) and enforces access on read.
"""

from app.platform.production.knowledge.version import (
    KNOWLEDGE_ACTIVE,
    KNOWLEDGE_DRAFT,
    KnowledgeDocument,
    content_checksum,
)


class KnowledgeIngestionService:

    def __init__(self, access_control=None):
        self.access_control = access_control
        self._documents = {}

    def ingest(self, document_id, tenant_id, content, source="", version="1.0"):
        document = KnowledgeDocument(
            document_id=document_id, version=version, tenant_id=tenant_id,
            source=source, checksum=content_checksum(content),
            status=KNOWLEDGE_DRAFT,
        )
        self._documents[(document_id, version)] = document
        return document

    def activate(self, document_id, version="1.0"):
        document = self._documents[(document_id, version)]
        activated = KnowledgeDocument(
            document_id=document.document_id, version=document.version,
            tenant_id=document.tenant_id, source=document.source,
            checksum=document.checksum, status=KNOWLEDGE_ACTIVE,
            created_at=document.created_at,
        )
        self._documents[(document_id, version)] = activated
        return activated

    def get(self, document_id, version="1.0", agent_id=None):
        document = self._documents.get((document_id, version))
        if document is None:
            return None
        if self.access_control is not None and agent_id is not None:
            self.access_control.authorize(document_id, agent_id)
        return document

    def versions(self, document_id):
        return sorted(
            version for (doc_id, version) in self._documents
            if doc_id == document_id
        )


__all__ = ["KnowledgeIngestionService"]
