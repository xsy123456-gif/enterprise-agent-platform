"""Knowledge document versioning (Phase 15.5)."""

import hashlib
from dataclasses import dataclass, field

from app.core.time import utc_now

KNOWLEDGE_DRAFT = "DRAFT"
KNOWLEDGE_ACTIVE = "ACTIVE"
KNOWLEDGE_ARCHIVED = "ARCHIVED"
KNOWLEDGE_STATUSES = frozenset({KNOWLEDGE_DRAFT, KNOWLEDGE_ACTIVE,
                                KNOWLEDGE_ARCHIVED})


def content_checksum(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class KnowledgeDocument:
    document_id: str
    version: str
    tenant_id: str
    source: str = ""
    checksum: str = ""
    status: str = KNOWLEDGE_DRAFT
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        if not self.document_id:
            raise ValueError("document_id is required")
        if not self.version:
            raise ValueError("version is required")
        if not self.tenant_id:
            raise ValueError("tenant_id is required")
        if self.status not in KNOWLEDGE_STATUSES:
            raise ValueError(f"unknown knowledge status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "version": self.version,
            "tenant_id": self.tenant_id,
            "source": self.source,
            "checksum": self.checksum,
            "status": self.status,
            "created_at": self.created_at,
        }


__all__ = [
    "KnowledgeDocument",
    "content_checksum",
    "KNOWLEDGE_STATUSES",
    "KNOWLEDGE_DRAFT",
    "KNOWLEDGE_ACTIVE",
    "KNOWLEDGE_ARCHIVED",
]
