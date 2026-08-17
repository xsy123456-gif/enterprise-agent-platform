"""Knowledge package (Phase 15.5 / 18.11)."""

from app.platform.production.knowledge.access import (
    KnowledgeAccessControl,
    KnowledgeAccessPolicy,
)
from app.platform.production.knowledge.evaluation import (
    KnowledgeEvaluation,
    KnowledgeEvaluationStore,
)
from app.platform.production.knowledge.ingestion import KnowledgeIngestionService
from app.platform.production.knowledge.management_repository import (
    InMemoryKnowledgeManagementRepository,
    KnowledgeManagementRepository,
)
from app.platform.production.knowledge.projection import KnowledgeProjectionService
from app.platform.production.knowledge.serving import (
    InMemoryKnowledgeServing,
    KnowledgeServingPort,
)
from app.platform.production.knowledge.version import KnowledgeDocument

__all__ = [
    "KnowledgeDocument",
    "KnowledgeIngestionService",
    "KnowledgeAccessPolicy",
    "KnowledgeAccessControl",
    "KnowledgeEvaluation",
    "KnowledgeEvaluationStore",
    "KnowledgeManagementRepository",
    "InMemoryKnowledgeManagementRepository",
    "KnowledgeServingPort",
    "InMemoryKnowledgeServing",
    "KnowledgeProjectionService",
]
