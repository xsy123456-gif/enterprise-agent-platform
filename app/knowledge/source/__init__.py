"""Knowledge Source Layer — enterprise knowledge ingress boundary.

Discovers and reads enterprise knowledge files (PDF / DOCX / TXT) into the
platform's ``SourceDocument`` model.  It never chunks, embeds, or touches the
RAG engine; those belong to the ingestion layer.
"""

from app.knowledge.source.base import KnowledgeSourcePort
from app.knowledge.source.errors import (
    KnowledgeSourceError,
    KnowledgeSourceNotFoundError,
    KnowledgeSourceReadError,
)
from app.knowledge.source.models import KnowledgeSourceDocument
from app.knowledge.source.scanner import KnowledgeSourceScanner

__all__ = [
    "KnowledgeSourcePort",
    "KnowledgeSourceDocument",
    "KnowledgeSourceScanner",
    "KnowledgeSourceError",
    "KnowledgeSourceNotFoundError",
    "KnowledgeSourceReadError",
]
