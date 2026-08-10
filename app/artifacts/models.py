from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class AgentLifecycleStatus:
    """Artifact lifecycle contract, independent from governance implementation."""

    DRAFT = "draft"
    VALIDATING = "validating"
    COMPILING = "compiling"
    COMPILED = "compiled"
    APPROVED = "approved"
    PUBLISHED = "published"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"

    ALL = {
        DRAFT, VALIDATING, COMPILING, COMPILED, APPROVED, PUBLISHED, ACTIVE,
        DEPRECATED, ARCHIVED,
    }
    TRANSITIONS = {
        DRAFT: {VALIDATING, ARCHIVED},
        VALIDATING: {COMPILING, DRAFT, ARCHIVED},
        COMPILING: {COMPILED, DRAFT, ARCHIVED},
        COMPILED: {APPROVED, DRAFT, ARCHIVED},
        APPROVED: {PUBLISHED, DEPRECATED, ARCHIVED},
        PUBLISHED: {ACTIVE, DEPRECATED, ARCHIVED},
        ACTIVE: {DEPRECATED, ARCHIVED},
        DEPRECATED: {ARCHIVED},
        ARCHIVED: set(),
    }

    @classmethod
    def transition(cls, current, target):
        if current not in cls.ALL or target not in cls.ALL:
            raise ValueError(f"Unsupported Agent lifecycle transition: {current} -> {target}")
        if target not in cls.TRANSITIONS[current]:
            raise ValueError(f"Invalid Agent lifecycle transition: {current} -> {target}")
        return target


@dataclass(frozen=True)
class CompiledAgentArtifact:
    artifact_id: str
    agent_id: str
    agent_version: str
    graph_hash: str
    compiler_version: str
    graph_ir: Any
    dependencies: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    status: str = AgentLifecycleStatus.COMPILED

    def __post_init__(self):
        for name in ("artifact_id", "agent_id", "agent_version", "graph_hash", "compiler_version"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if self.status not in AgentLifecycleStatus.ALL:
            raise ValueError(f"Unsupported artifact status: {self.status}")

    @classmethod
    def from_ir(cls, graph_ir, compiler_version, dependencies=None):
        graph_hash = graph_ir.stable_hash()
        return cls(
            artifact_id=f"{graph_ir.agent_id}:{graph_ir.version}:{graph_hash[:12]}",
            agent_id=graph_ir.agent_id,
            agent_version=graph_ir.version,
            graph_hash=graph_hash,
            compiler_version=compiler_version,
            graph_ir=graph_ir,
            dependencies=dict(dependencies or {}),
        )
