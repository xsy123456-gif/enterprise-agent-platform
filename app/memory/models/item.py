from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def utc_now():
    return datetime.now(timezone.utc)


class MemoryItemStatus:
    ACTIVE = "active"
    REPLACED = "replaced"
    CONFLICT = "conflict"


@dataclass
class MemoryItem:
    memory_key: str
    type: str
    content: Any
    importance: float
    confidence: float
    source: str
    tenant_id: str
    department_id: str | None
    user_id: str
    agent_id: str
    embedding: list[float] | None = None
    version: int = 1
    status: str = MemoryItemStatus.ACTIVE
    replaces_id: str | None = None
    replaced_by_id: str | None = None
    access_count: int = 0
    last_accessed_at: datetime | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
