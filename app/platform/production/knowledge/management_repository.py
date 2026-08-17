"""Knowledge management repository port (Phase 18.10 / 18.11).

The Management Plane stores knowledge *documents* (metadata + content) with
version + checksum.  This is durable business state; a future PostgreSQL
adapter swaps in behind the port with zero Management Service change.  The
Serving Plane (retrieval/ACL/citation) is a separate boundary.
"""

from abc import ABC, abstractmethod


class KnowledgeManagementRepository(ABC):
    @abstractmethod
    def put(self, document_id, version, document, content):
        pass

    @abstractmethod
    def get(self, document_id, version=None):
        pass

    @abstractmethod
    def get_with_content(self, document_id, version):
        pass

    @abstractmethod
    def versions(self, document_id):
        pass


class InMemoryKnowledgeManagementRepository(KnowledgeManagementRepository):

    def __init__(self):
        self._documents = {}  # (document_id, version) -> (document, content)
        self._active = {}

    def put(self, document_id, version, document, content):
        self._documents[(document_id, version)] = (document, content)
        if document.status == "ACTIVE":
            self._active[document_id] = version
        return document

    def get(self, document_id, version=None):
        version = version or self._active.get(document_id)
        if version is None:
            versions = self.versions(document_id)
            version = versions[0] if versions else None
        if version is None:
            return None
        entry = self._documents.get((document_id, version))
        return entry[0] if entry else None

    def get_with_content(self, document_id, version):
        return self._documents.get((document_id, version))

    def versions(self, document_id):
        return sorted(
            version for (doc_id, version) in self._documents
            if doc_id == document_id
        )


__all__ = [
    "KnowledgeManagementRepository",
    "InMemoryKnowledgeManagementRepository",
]
