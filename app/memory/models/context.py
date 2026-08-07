from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class MemoryReference:
    memory_id: str
    type: str
    entity_id: str = ""
    attribute: str = ""
    content: Any = None
    confidence: float = 0.0
    importance: float = 0.0
    relevance_score: float = 0.0
    created_at: datetime | None = None


@dataclass(frozen=True)
class MemoryContext:
    summary: str = ""
    references: list[MemoryReference] = field(default_factory=list)


# ── Public API aliases (Group 3) ─────────────────────────────────

MemoryRecord = MemoryReference
MemoryReadResult = MemoryContext
