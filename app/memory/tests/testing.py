"""Public test builder — for contract/seal tests only.

Provides build_test_memory() and build_test_memory_with_spies()
that return fully functional MemorySystem instances with in-memory doubles.
No real PostgreSQL or external LLM/Embedding needed.
"""

from dataclasses import dataclass, field

from app.memory.factory import MemoryClient, MemoryRuntime, MemorySystem


@dataclass
class SpyCounters:
    save_event_calls: int = 0
    embed_calls: int = 0


def build_test_memory():
    """Return a MemorySystem wired with in-memory doubles."""
    from app.memory.memory_test import _InMemoryEmbeddingService, _InMemoryRepository, StubLLM
    from app.memory.factory import build_memory_system
    from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
    from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider

    repo = _InMemoryRepository()
    return build_memory_system(
        repository=repo,
        embedding_service=_InMemoryEmbeddingService(),
        extractor=StructuredMemoryExtractor(),
        text_model=StubLLM(),
        authorization_provider=AllowAllMemoryAuthorizationProvider(),
    )


def build_test_memory_with_spies():
    """Return (MemorySystem, SpyCounters) with spy-instrumented doubles.

    The spy counters track save_event calls and embed calls so that
    boundary tests can verify side-effect isolation without importing
    internal modules directly.
    """
    from app.memory.memory_test import _InMemoryEmbeddingService, _InMemoryRepository, StubLLM
    from app.memory.factory import build_memory_system
    from app.memory.pipeline.write.extractor import StructuredMemoryExtractor
    from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider

    counters = SpyCounters()

    repo = _InMemoryRepository()
    _orig_save = repo.save_event
    def _spy_save(event):
        counters.save_event_calls += 1
        return _orig_save(event)
    repo.save_event = _spy_save

    embed = _InMemoryEmbeddingService()
    _orig_embed = embed.embed
    def _spy_embed(text):
        counters.embed_calls += 1
        return _orig_embed(text)
    embed.embed = _spy_embed

    system = build_memory_system(
        repository=repo,
        embedding_service=embed,
        extractor=StructuredMemoryExtractor(),
        text_model=StubLLM(),
        authorization_provider=AllowAllMemoryAuthorizationProvider(),
    )
    return system, counters
