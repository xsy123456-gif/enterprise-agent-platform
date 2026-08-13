"""Knowledge runtime lifecycle (start / stop / health).

Knowledge failure must not prevent the platform from starting.  Health is
reported per-subcomponent so the composition root can surface ``degraded``.
"""

from app.knowledge.api.service import KnowledgeService
from app.knowledge.ingestion.service import KnowledgeIngestionService


class KnowledgeRuntime:
    def __init__(
        self,
        service: KnowledgeService | None = None,
        ingestion: KnowledgeIngestionService | None = None,
    ):
        self.service = service
        self.ingestion = ingestion
        self._started = False

    def start(self):
        self._started = True
        return True

    def stop(self, timeout=None):
        self._started = False
        return True

    def health(self) -> dict:
        return {
            "name": "knowledge",
            "healthy": self._started,
            "retriever": self._component_health(self.service.retriever),
            "ingestion": self._component_health(self.ingestion),
        }

    @staticmethod
    def _component_health(component):
        if component is None:
            return {"healthy": False, "error": "not wired"}
        checker = getattr(component, "health", None)
        if callable(checker):
            try:
                return checker()
            except Exception as error:
                return {"healthy": False, "error": str(error)}
        return {"healthy": True}
