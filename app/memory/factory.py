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


class MemoryClient:
    """Public Memory API — read() and write() only.

    Internal implementation delegates to MemoryService via mappers.
    """

    def __init__(self, service: MemoryService):
        self._service = service

    def read(self, request):
        from app.memory.api.mappers import from_context, to_retrieve_request
        internal = to_retrieve_request(request)
        context = self._service.retrieve(internal)
        return from_context(context)

    def write(self, request):
        from app.memory.api.mappers import from_submit_response, to_submit_request
        internal = to_submit_request(request)
        response = self._service.submit(internal)
        return from_submit_response(response)

class MemoryRuntime:
    """Lifecycle controller — start, stop, health. NOT part of the Agent API."""

    def __init__(self, worker: MemoryWorker):
        self._worker = worker
        self.running = False

    def start(self):
        if self.running:
            return
        self._worker.start()
        self.running = True

    def stop(self, timeout=None):
        if not self.running:
            return False
        result = self._worker.stop(timeout)
        if result:
            self.running = False
        return result

    def health(self):
        return self._worker.health()

    @property
    def connection_factory(self):
        return getattr(self._worker.repository, "connection_factory", None)


@dataclass(frozen=True)
class MemorySystem:
    """Built Memory subsystem — client for Agent, runtime for Composition Root."""
    client: MemoryClient
    runtime: MemoryRuntime

    def read(self, request):
        return self.client.read(request)

    def write(self, request):
        return self.client.write(request)


Memory = MemoryClient  # convenience alias


def build_memory_system(
    repository=None, embedding_service=None, extractor=None, compressor=None,
    duplicate_judge=None, authorization_provider: MemoryAuthorizationProvider = None,
    event_sink: MemoryEventSink = None, config=None, text_model=None,
):
    """Build Memory. Returns MemorySystem(client, runtime).

    The factory does NOT auto-start the worker.
    Call system.runtime.start() explicitly.
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
    if duplicate_judge is None:
        if text_model is not None:
            duplicate_judge = LLMSemanticDuplicateJudge(text_model)
        else:
            duplicate_judge = None
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
    worker = MemoryWorker(
        repository, write_pipeline, event_sink=event_sink, claim_limit=1,
    )
    client = MemoryClient(service)
    runtime = MemoryRuntime(worker)
    return MemorySystem(client=client, runtime=runtime)


def _repository_from_environment(config=None):
    config = config or MemoryDatabaseConfig.from_environment()
    return create_postgres_repository(
        config.url,
        embedding_dimension=config.embedding_dimension,
        initialize=config.initialize,
    )
