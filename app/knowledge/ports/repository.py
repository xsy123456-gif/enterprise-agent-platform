"""Knowledge repository port — document/chunk metadata storage.

Separated from the retriever so that audit trails can resolve chunk_id ->
original evidence without storing full content in the audit log.
"""

from abc import ABC, abstractmethod
from typing import Any


class KnowledgeRepositoryPort(ABC):
    @abstractmethod
    async def get_document(self, document_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    @abstractmethod
    async def list_versions(self, document_id: str) -> list[str]:
        raise NotImplementedError
