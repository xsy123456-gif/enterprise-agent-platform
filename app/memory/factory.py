from app.audit.memory import MemoryAuditSubscriber
from app.memory.adapter.runtime import RuntimeMemoryAdapter
from app.memory.api.service import MemoryService
from app.memory.consumer.event_consumer import MemoryEventConsumer
from app.memory.config import MemoryDatabaseConfig
from app.memory.events import MemoryEventPublisher
from app.memory.governance.policy import MemoryGovernancePolicy
from app.memory.pipeline.read.builder import ReadPipeline
from app.memory.pipeline.read.compressor import MemoryCompressor
from app.memory.pipeline.read.context_builder import MemoryContextBuilder
from app.memory.pipeline.read.deduplicator import MemoryReadDeduplicator
from app.memory.pipeline.read.fine_ranker import MemoryFineRanker
from app.memory.pipeline.read.pre_ranker import MemoryPreRanker
from app.memory.pipeline.read.retriever import MemoryRetriever
from app.memory.pipeline.read.scope_filter import MemoryScopeFilter
from app.memory.pipeline.write.builder import WritePipeline
from app.memory.pipeline.write.evaluator import MemoryEvaluator
from app.memory.pipeline.write.extractor import LLMMemoryExtractor
from app.memory.pipeline.write.fine_dedup import MemoryFineDeduplicator
from app.memory.pipeline.write.normalizer import MemoryNormalizer
from app.memory.pipeline.write.pre_dedup import MemoryPreDeduplicator
from app.memory.pipeline.write.ranker import MemoryRanker
from app.memory.pipeline.write.resolver import MemoryResolver
from app.memory.pipeline.write.updater import MemoryUpdater
from app.memory.storage.postgres import create_postgres_repository


def build_memory_system(llm, event_bus, repository=None, extractor=None, async_mode=True,
                        governance=None):
    repository = repository or _repository_from_environment()
    governance = governance or MemoryGovernancePolicy()
    publisher = MemoryEventPublisher(event_bus)
    read_pipeline = ReadPipeline(
        MemoryScopeFilter(governance), MemoryRetriever(repository),
        MemoryPreRanker(), MemoryFineRanker(), MemoryReadDeduplicator(),
        MemoryCompressor(llm), MemoryContextBuilder(), repository,
    )
    service = MemoryService(repository, read_pipeline, publisher)
    write_pipeline = WritePipeline(
        repository, extractor or LLMMemoryExtractor(llm), MemoryEvaluator(),
        MemoryNormalizer(), MemoryPreDeduplicator(), MemoryResolver(),
        MemoryFineDeduplicator(), MemoryRanker(), MemoryUpdater(repository),
        governance, publisher,
    )
    consumer = MemoryEventConsumer(
        service, repository, write_pipeline, async_mode=async_mode
    )
    event_bus.subscribe(consumer)
    audit = MemoryAuditSubscriber()
    event_bus.subscribe(audit)
    return service, consumer, RuntimeMemoryAdapter(service), audit


def _repository_from_environment():
    config = MemoryDatabaseConfig.from_environment()
    return create_postgres_repository(
        config.url,
        embedding_dimension=config.embedding_dimension,
        initialize=config.initialize,
    )
