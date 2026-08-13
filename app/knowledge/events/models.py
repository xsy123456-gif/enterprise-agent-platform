"""Knowledge event models.

EventBus payloads carry IDs, status and metadata only — never full chunk text.
"""

from enum import Enum


class KnowledgeEventType(str, Enum):
    RETRIEVAL_STARTED = "knowledge.retrieval.started"
    RETRIEVAL_COMPLETED = "knowledge.retrieval.completed"
    RETRIEVAL_DENIED = "knowledge.retrieval.denied"
    INGESTION_STARTED = "knowledge.ingestion.started"
    INGESTION_COMPLETED = "knowledge.ingestion.completed"
    DOCUMENT_UPDATED = "knowledge.document.updated"
    DOCUMENT_DELETED = "knowledge.document.deleted"
