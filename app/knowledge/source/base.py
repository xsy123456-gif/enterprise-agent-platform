"""Knowledge source port.

The Knowledge Core must never know where enterprise knowledge files live.  A
source adapter (local filesystem, MinIO, ...) implements this port so the
storage backend can be replaced without touching the core.
"""

from abc import ABC, abstractmethod

from app.knowledge.models.document import SourceDocument
from app.knowledge.source.models import KnowledgeSourceDocument


class KnowledgeSourcePort(ABC):
    @abstractmethod
    def list_documents(self) -> list[KnowledgeSourceDocument]:
        """Discover available knowledge source files."""
        raise NotImplementedError

    @abstractmethod
    def read_document(self, source_id: str) -> SourceDocument:
        """Read a source file into a platform ``SourceDocument`` (content + ACL)."""
        raise NotImplementedError

    @abstractmethod
    def read_parts(self, source_id: str) -> list[SourceDocument]:
        """Read a source file as per-page (PDF) / per-section (DOCX) documents."""
        raise NotImplementedError
