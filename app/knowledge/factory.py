"""Knowledge subsystem composition.

``build_knowledge`` is the composition-root entrypoint.  It wires a retriever
adapter (the only place Haystack/Qdrant may appear) behind the
``KnowledgeRetrieverPort`` and returns a ``KnowledgeSystem``.
"""

from dataclasses import dataclass

from app.knowledge.access.resolver import ScopeResolver
from app.knowledge.api.service import KnowledgeService
from app.knowledge.config import KnowledgeConfig
from app.knowledge.ingestion.service import KnowledgeIngestionService
from app.knowledge.ports.ingestion import KnowledgeIngestionPort
from app.knowledge.ports.retriever import KnowledgeRetrieverPort
from app.knowledge.runtime import KnowledgeRuntime


@dataclass(frozen=True)
class KnowledgeSystem:
    service: KnowledgeService
    runtime: KnowledgeRuntime
    config: KnowledgeConfig

    async def retrieve(self, request, access_context):
        return await self.service.retrieve(request, access_context)


def build_knowledge(
    retriever: KnowledgeRetrieverPort,
    ingestion: KnowledgeIngestionPort | None = None,
    config: KnowledgeConfig | None = None,
    event_bus=None,
    resolver: ScopeResolver | None = None,
) -> KnowledgeSystem:
    """Assemble the Knowledge subsystem.

    The retriever adapter is injected; knowledge core never imports the backend.
    """
    if retriever is None:
        raise ValueError("build_knowledge requires a KnowledgeRetrieverPort")
    config = config or KnowledgeConfig()
    service = KnowledgeService(
        retriever=retriever,
        config=config,
        resolver=resolver,
        event_bus=event_bus,
    )
    ingestion_service = (
        KnowledgeIngestionService(ingestion, event_bus=event_bus)
        if ingestion is not None
        else None
    )
    runtime = KnowledgeRuntime(service=service, ingestion=ingestion_service)
    return KnowledgeSystem(service=service, runtime=runtime, config=config)
