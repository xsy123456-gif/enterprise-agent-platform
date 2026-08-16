"""Knowledge ingestion service (Phase 15.5 / 18.11).

Management Plane: ingest -> checksum -> version -> activate.  On activation the
``KnowledgeProjectionService`` projects the ACTIVE document into the Serving
Plane; the Serving Plane (not this service) performs agent retrieval / ACL /
citation.
"""

from dataclasses import replace

from app.platform.production.knowledge.management_repository import (
    InMemoryKnowledgeManagementRepository,
)
from app.platform.production.knowledge.version import (
    KNOWLEDGE_ACTIVE,
    KNOWLEDGE_DRAFT,
    KnowledgeDocument,
    content_checksum,
)


class KnowledgeIngestionService:

    def __init__(self, repository=None, projection=None, access_control=None):
        self.repository = repository or InMemoryKnowledgeManagementRepository()
        self.projection = projection
        self.access_control = access_control

    def ingest(self, document_id, tenant_id, content, source="", version="1.0"):
        document = KnowledgeDocument(
            document_id=document_id, version=version, tenant_id=tenant_id,
            source=source, checksum=content_checksum(content),
            status=KNOWLEDGE_DRAFT,
        )
        self.repository.put(document_id, version, document, content)
        return document

    def activate(self, document_id, version="1.0"):
        entry = self.repository.get_with_content(document_id, version)
        document, content = entry
        activated = replace(document, status=KNOWLEDGE_ACTIVE)
        self.repository.put(document_id, version, activated, content)
        if self.projection is not None:
            self.projection.project(activated, content)
        return activated

    def get(self, document_id, version="1.0", agent_id=None):
        document = self.repository.get(document_id, version)
        if document is None:
            return None
        if self.access_control is not None and agent_id is not None:
            self.access_control.authorize(document_id, agent_id)
        return document

    def versions(self, document_id):
        return self.repository.versions(document_id)


__all__ = ["KnowledgeIngestionService"]
