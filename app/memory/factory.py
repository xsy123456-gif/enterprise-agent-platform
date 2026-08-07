from dataclasses import dataclass

from app.memory.api.service import MemoryService
from app.memory.config import MemoryDatabaseConfig
from app.memory.embedding.factory import create_embedding_service
from app.memory.events import MemoryEventSink
from app.memory.pipeline.read.builder import ReadPipeline
from app.memory.pipeline.read.compressor import MemoryCompressor
from app.memory.pipeline.read.context_builder import MemoryContextBuilder
from app.memory.pipeline.read.deduplicator import MemoryReadDeduplicator
from app.memory.pipeline.read.fine_ranker import MemoryFineRanker
from app.memory.pipeline.read.fusion import MemoryCandidateFusion
from app.memory.pipeline.read.pre_ranker import MemoryPreRanker
from app.memory.pipeline.read.query_analyzer import MemoryQueryAnalyzer
from app.memory.pipeline.read.retriever import MemoryRetriever
from app.memory.pipeline.read.scope_filter import MemoryScopeFilter
from app.memory.pipeline.write.builder import WritePipeline
from app.memory.pipeline.write.evaluator import MemoryEvaluator
from app.memory.pipeline.write.extractor import LLMMemoryExtractor
from app.memory.pipeline.write.fine_dedup import (
    LLMSemanticDuplicateJudge, MemoryFineDeduplicator,
)
from app.memory.pipeline.write.normalizer import MemoryNormalizer
from app.memory.pipeline.write.pre_dedup import MemoryPreDeduplicator
from app.memory.pipeline.write.ranker import MemoryRanker
from app.memory.pipeline.write.resolver import MemoryResolver
from app.memory.pipeline.write.updater import MemoryUpdater
from app.memory.ports.authorization import MemoryAuthorizationProvider
from app.memory.storage.postgres import create_postgres_repository
from app.memory.worker.event_worker import MemoryWorker


@dataclass
class MemorySystem:
    _service: MemoryService
    _worker: MemoryWorker

    def retrieve(self, request):
        return self._service.retrieve(request)

    def submit(self, request):
        return self._service.submit(request)


def build_memory_system(
    repository=None, embedding_service=None, extractor=None, compressor=None,
    duplicate_judge=None, authorization_provider: MemoryAuthorizationProvider = None,
    event_sink: MemoryEventSink = None, config=None, text_model=None,
    async_mode=True,
):
    """Build Memory with only Memory ports and dependencies.

    Platform adapters (Runtime state, EventBus, audit) belong outside this factory.
    A production composition root must explicitly provide authorization_provider.
    """
    if authorization_provider is None:
        raise ValueError("authorization_provider is required; choose an explicit policy")
    repository = repository or _repository_from_environment(config)
    embedding_service = embedding_service or create_embedding_service(
        repository.embedding_dimension
    )
    if extractor is None:
        if text_model is None:
            raise ValueError("text_model is required when extractor is not provided")
        extractor = LLMMemoryExtractor(text_model)
    compressor = compressor or MemoryCompressor(text_model)
    duplicate_judge = duplicate_judge or LLMSemanticDuplicateJudge(text_model)
    read_pipeline = ReadPipeline(
        MemoryScopeFilter(authorization_provider),
        MemoryRetriever(
            repository, MemoryQueryAnalyzer(), embedding_service,
            MemoryCandidateFusion(),
        ),
        MemoryPreRanker(), MemoryFineRanker(), MemoryReadDeduplicator(),
        compressor, MemoryContextBuilder(), repository,
    )
    service = MemoryService(
        repository, read_pipeline, authorization_provider, event_sink
    )
    write_pipeline = WritePipeline(
        repository, extractor, embedding_service, MemoryEvaluator(),
        MemoryNormalizer(), MemoryPreDeduplicator(), MemoryResolver(),
        MemoryFineDeduplicator(duplicate_judge), MemoryRanker(),
        MemoryUpdater(repository), authorization_provider, None,
    )
    worker = MemoryWorker(repository, write_pipeline, event_sink=event_sink)
    if async_mode:
        worker.start()
    return MemorySystem(service, worker)


def _repository_from_environment(config=None):
    config = config or MemoryDatabaseConfig.from_environment()
    return create_postgres_repository(
        config.url,
        embedding_dimension=config.embedding_dimension,
        initialize=config.initialize,
    )
