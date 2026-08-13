"""Knowledge ingestion port — control plane only.

Agents must never reach this surface.  Ingestion is driven by the platform
control plane (manual upload, connectors, sync jobs).
"""

from abc import ABC, abstractmethod

from app.knowledge.models.document import SourceDocument


class KnowledgeIngestionPort(ABC):
    @abstractmethod
    async def ingest(self, document: SourceDocument) -> str:
        """Ingest a source document, returning its stable document_id."""
        raise NotImplementedError

    @abstractmethod
    async def update(self, document: SourceDocument) -> str:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, document_id: str, version: str | None = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def reindex(self, document_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def set_acl(self, document_id: str, access_policy: dict) -> None:
        raise NotImplementedError
