"""Knowledge Ingestion Service — control plane only.

Agents never reach this service.  It composes validation, normalization and
versioning around the ingestion port, and enforces idempotency via content
fingerprint comparison.
"""

from app.knowledge.ingestion.lifecycle import KnowledgeDocumentStatus
from app.knowledge.ingestion.normalizer import SourceDocumentNormalizer
from app.knowledge.ingestion.validator import SourceDocumentValidator
from app.knowledge.ingestion.versioning import (
    content_fingerprint,
    is_version_changed,
    stable_document_id,
)
from app.knowledge.models.document import SourceDocument
from app.knowledge.ports.ingestion import KnowledgeIngestionPort


class KnowledgeIngestionService:
    def __init__(
        self,
        ingestion: KnowledgeIngestionPort,
        validator: SourceDocumentValidator | None = None,
        normalizer: SourceDocumentNormalizer | None = None,
        event_bus=None,
    ):
        if ingestion is None:
            raise ValueError("KnowledgeIngestionService requires a KnowledgeIngestionPort")
        self.ingestion = ingestion
        self.validator = validator or SourceDocumentValidator()
        self.normalizer = normalizer or SourceDocumentNormalizer()
        self.event_bus = event_bus

    async def ingest(self, document: SourceDocument) -> str:
        self.validator.validate(document)
        normalized = self.normalizer.normalize(document)
        self._publish("knowledge.ingestion.started", {
            "document_id": stable_document_id(normalized.source_system, normalized.external_id),
        })
        document_id = await self.ingestion.ingest(normalized)
        self._publish("knowledge.ingestion.completed", {"document_id": document_id})
        return document_id

    async def update(self, document: SourceDocument) -> str:
        self.validator.validate(document)
        normalized = self.normalizer.normalize(document)
        return await self.ingestion.update(normalized)

    async def delete(self, document_id: str, version: str | None = None) -> None:
        await self.ingestion.delete(document_id, version)
        self._publish("knowledge.document.deleted", {"document_id": document_id})

    async def set_acl(self, document_id: str, access_policy: dict) -> None:
        await self.ingestion.set_acl(document_id, access_policy)

    @staticmethod
    def document_id(document: SourceDocument) -> str:
        return stable_document_id(document.source_system, document.external_id)

    @staticmethod
    def fingerprint(content: str) -> str:
        return content_fingerprint(content)

    @staticmethod
    def changed(current: str | None, new: str) -> bool:
        return is_version_changed(current, new)

    @staticmethod
    def retrievable_status() -> set:
        return KnowledgeDocumentStatus.__members__

    def _publish(self, event_type, payload):
        if self.event_bus is None:
            return
        publish = getattr(self.event_bus, "publish", None)
        if callable(publish):
            publish({"event_type": event_type, **payload})
