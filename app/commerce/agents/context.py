"""Agent runtime context + memory/knowledge ports (Phase 12.5 / 12.6).

Memory and Knowledge are *context* boundaries only:

- Memory provides user preference / task-history / analysis-summary context and
  stores interaction summaries after the fact.  It is never a business data
  source.
- Knowledge (v1 OFF) provides explanatory references only; it never participates
  in cause / diagnosis.

Data priority (v1): Commerce Facts > Knowledge > Memory.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class AgentMemoryPort(ABC):
    """Thin worker-facing memory boundary (retrieve/submit)."""

    @abstractmethod
    def retrieve(self, query, limit=10) -> list[str]:
        pass

    @abstractmethod
    def submit(self, summary: str) -> None:
        pass


class AgentKnowledgePort(ABC):
    """Thin worker-facing knowledge boundary (retrieve only)."""

    @abstractmethod
    def retrieve(self, query) -> list[str]:
        pass


DATA_PRIORITY = ("commerce_facts", "knowledge", "memory")


@dataclass(frozen=True)
class AgentContext:
    """Assembled runtime context for one request.

    ``trusted_context`` is the Runtime-injected ``TrustedExecutionContext`` —
    the only source of tenant / principal / scope.  Memory and knowledge are
    optional context snippets; neither is a business fact source.
    """

    trusted_context: object
    memory_snippets: tuple[str, ...] = ()
    knowledge_snippets: tuple[str, ...] = ()
    history_turns: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "memory_snippets", tuple(self.memory_snippets or ()))
        object.__setattr__(self, "knowledge_snippets", tuple(self.knowledge_snippets or ()))
        object.__setattr__(self, "history_turns", tuple(self.history_turns or ()))


__all__ = [
    "AgentMemoryPort",
    "AgentKnowledgePort",
    "AgentContext",
    "DATA_PRIORITY",
]
