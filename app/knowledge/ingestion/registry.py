"""Document registry for the ingestion control plane.

``DocumentRegistry`` stores the original ``SourceDocument`` plus ACL/index
version counters so ``reindex`` can reprocess a document without changing its
business identity.  Two implementations:

* ``InMemoryDocumentRegistry`` — tests / single-process.
* ``PostgresDocumentRegistry`` — durable; survives restarts (Freeze requirement).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
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
    ingestion_status: str = "indexed"


class DocumentRegistry(ABC):
    @abstractmethod
    def put(self, record: DocumentRecord) -> DocumentRecord:
        raise NotImplementedError

    @abstractmethod
    def get(self, document_id: str) -> DocumentRecord | None:
        raise NotImplementedError

    @abstractmethod
    def remove(self, document_id: str) -> DocumentRecord | None:
        raise NotImplementedError


class InMemoryDocumentRegistry(DocumentRegistry):
    def __init__(self):
        self._records: dict[str, DocumentRecord] = {}

    def put(self, record: DocumentRecord) -> DocumentRecord:
        self._records[record.document_id] = record
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        return self._records.get(document_id)

    def remove(self, document_id: str) -> DocumentRecord | None:
        return self._records.pop(document_id, None)


class PostgresDocumentRegistry(DocumentRegistry):
    """Durable document registry backed by PostgreSQL.

    ``connection_factory`` is a callable returning a context manager that yields
    a psycopg connection (e.g. ``PostgresProvider.connection_factory``).
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS knowledge_documents (
      document_id TEXT PRIMARY KEY,
      source_system TEXT NOT NULL,
      external_id TEXT NOT NULL,
      tenant_id TEXT NOT NULL,
      source_version TEXT NOT NULL,
      document_type TEXT,
      title TEXT,
      content TEXT NOT NULL,
      language TEXT,
      source_updated_at TEXT,
      metadata JSONB NOT NULL DEFAULT '{}',
      access_policy JSONB NOT NULL DEFAULT '{}',
      acl_version INTEGER NOT NULL DEFAULT 1,
      index_version INTEGER NOT NULL DEFAULT 1,
      ingestion_status TEXT NOT NULL DEFAULT 'indexed',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """

    def __init__(self, connection_factory):
        if connection_factory is None:
            raise ValueError("PostgresDocumentRegistry requires connection_factory")
        self.connection_factory = connection_factory

    def initialize_schema(self):
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(self.SCHEMA)
            conn.commit()

    def put(self, record: DocumentRecord) -> DocumentRecord:
        document = record.document
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO knowledge_documents
                      (document_id, source_system, external_id, tenant_id,
                       source_version, document_type, title, content, language,
                       source_updated_at, metadata, access_policy, acl_version,
                       index_version, ingestion_status, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (document_id) DO UPDATE SET
                      source_version = EXCLUDED.source_version,
                      document_type = EXCLUDED.document_type,
                      title = EXCLUDED.title,
                      content = EXCLUDED.content,
                      language = EXCLUDED.language,
                      source_updated_at = EXCLUDED.source_updated_at,
                      metadata = EXCLUDED.metadata,
                      access_policy = EXCLUDED.access_policy,
                      acl_version = EXCLUDED.acl_version,
                      index_version = EXCLUDED.index_version,
                      ingestion_status = EXCLUDED.ingestion_status,
                      updated_at = NOW()
                    """,
                    (
                        record.document_id, record.source_system, record.external_id,
                        record.tenant_id, record.source_version, document.document_type,
                        document.title, document.content, document.language,
                        document.source_updated_at, json.dumps(document.metadata or {}),
                        json.dumps(record.access_policy or {}), record.acl_version,
                        record.index_version, record.ingestion_status,
                    ),
                )
            conn.commit()
        return record

    def get(self, document_id: str) -> DocumentRecord | None:
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT document_id, source_system, external_id, tenant_id,"
                    " source_version, document_type, title, content, language,"
                    " source_updated_at, metadata, access_policy, acl_version,"
                    " index_version, ingestion_status FROM knowledge_documents"
                    " WHERE document_id = %s",
                    (document_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def remove(self, document_id: str) -> DocumentRecord | None:
        record = self.get(document_id)
        with self.connection_factory() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM knowledge_documents WHERE document_id = %s",
                    (document_id,),
                )
            conn.commit()
        return record

    @staticmethod
    def _row_to_record(row) -> DocumentRecord:
        (
            document_id, source_system, external_id, tenant_id, source_version,
            document_type, title, content, language, source_updated_at, metadata,
            access_policy, acl_version, index_version, ingestion_status,
        ) = row
        document = SourceDocument(
            source_system=source_system,
            external_id=external_id,
            tenant_id=tenant_id,
            document_type=document_type or "",
            title=title or "",
            content=content or "",
            source_version=source_version,
            source_updated_at=source_updated_at,
            language=language,
            metadata=metadata if isinstance(metadata, dict) else json.loads(metadata or "{}"),
            access_policy=(
                access_policy if isinstance(access_policy, dict)
                else json.loads(access_policy or "{}")
            ),
        )
        return DocumentRecord(
            document_id=document_id,
            source_system=source_system,
            external_id=external_id,
            tenant_id=tenant_id,
            source_version=source_version,
            document=document,
            acl_version=acl_version,
            index_version=index_version,
            access_policy=document.access_policy,
            ingestion_status=ingestion_status,
        )
