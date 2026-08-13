"""In-memory document registry for the ingestion control plane.

Stores the original ``SourceDocument`` plus ACL/index version counters so
``reindex`` can reprocess a document without changing its business identity.
A durable repository (Postgres) is a later phase; the port surface is unchanged.
"""

from dataclasses import dataclass, field
from typing import Any

from app.knowledge.models.document import SourceDocument


@dataclass
class DocumentRecord:
    document_id: str
    source_system: str
    external_id: str
    tenant_id: str
    source_version: str
    document: SourceDocument
    acl_version: int = 1
    index_version: int = 1
    access_policy: dict[str, Any] = field(default_factory=dict)


class InMemoryDocumentRegistry:
    def __init__(self):
        self._records: dict[str, DocumentRecord] = {}

    def put(self, record: DocumentRecord) -> DocumentRecord:
        self._records[record.document_id] = record
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        return self._records.get(document_id)

    def remove(self, document_id: str) -> DocumentRecord | None:
        return self._records.pop(document_id, None)
