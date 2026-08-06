from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class MemoryReference:
    memory_id: str
    type: str
    confidence: float
    importance: float
    created_at: datetime


@dataclass(frozen=True)
class MemoryContext:
    summary: str = ""
    references: list[MemoryReference] = field(default_factory=list)
