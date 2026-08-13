"""Audit records for knowledge retrieval.

Audit stores references (IDs, scope, hashes, decision) — never full chunk
content.  Investigation follows chunk_id -> KnowledgeRepository.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KnowledgeRetrievalAuditRecord:
    retrieval_id: str
    user_id: str
    tenant_id: str
    query_hash: str
    decision: str
    execution_id: str | None = None
    trace_id: str | None = None
    requested_scope: dict = field(default_factory=dict)
    effective_scope: dict = field(default_factory=dict)
    document_ids: list[str] = field(default_factory=list)
    chunk_ids: list[str] = field(default_factory=list)
    result_count: int = 0
    timestamp: str = field(default_factory=utc_now)

    def to_dict(self):
        return {
            "retrieval_id": self.retrieval_id,
            "execution_id": self.execution_id,
            "trace_id": self.trace_id,
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "query_hash": self.query_hash,
            "requested_scope": dict(self.requested_scope),
            "effective_scope": dict(self.effective_scope),
            "document_ids": list(self.document_ids),
            "chunk_ids": list(self.chunk_ids),
            "result_count": self.result_count,
            "decision": self.decision,
            "timestamp": self.timestamp,
        }
