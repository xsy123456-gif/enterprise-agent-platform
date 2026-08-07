from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from app.memory.models.identity import MemoryIdentity
from app.memory.models.scope import MemoryScope


def utc_now():
    return datetime.now(timezone.utc)


class MemoryItemStatus:
    ACTIVE = "active"
    REPLACED = "replaced"
    CONFLICT = "conflict"
    ARCHIVED = "archived"


@dataclass
class MemoryItem:
    memory_key: str
    type: str
    entity_id: str
    attribute: str
    content: Any
    importance: float
    confidence: float
    source: str
    tenant_id: str
    department_id: str | None
    user_id: str
    agent_id: str
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_version: str | None = None
    embedding_dimension: int | None = None
    schema_version: int = 1
    version: int = 1
    status: str = MemoryItemStatus.ACTIVE
    replaces_id: str | None = None
    replaced_by_id: str | None = None
    access_count: int = 0
    observation_count: int = 1
    last_observed_at: datetime | None = None
    last_accessed_at: datetime | None = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def __post_init__(self):
        scope = self.scope
        identity = self.identity
        self.tenant_id = scope.tenant_id
        self.department_id = scope.department_id
        self.user_id = scope.user_id
        self.agent_id = scope.agent_id
        self.type = identity.type
        self.entity_id = identity.entity_id
        self.attribute = identity.attribute
        if not isinstance(self.schema_version, int) or self.schema_version < 1:
            raise ValueError("schema_version must be a positive integer")
        if not isinstance(self.observation_count, int) or self.observation_count < 0:
            raise ValueError("observation_count must be a non-negative integer")
        if self.last_observed_at is None:
            self.last_observed_at = self.created_at

    @property
    def scope(self):
        return MemoryScope(
            tenant_id=self.tenant_id,
            department_id=self.department_id,
            user_id=self.user_id,
            agent_id=self.agent_id,
        )

    @property
    def identity(self):
        return MemoryIdentity(
            type=self.type,
            entity_id=self.entity_id,
            attribute=self.attribute,
        )
