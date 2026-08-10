from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import hashlib
import json


def utc_now():
    return datetime.now(timezone.utc).isoformat()


SENSITIVE_KEYS = {"password", "api_key", "token", "secret", "credential"}


def reject_sensitive_data(value, path="artifact"):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower()
            is_reference = normalized.endswith("_ref") or normalized.endswith("_refs")
            is_sensitive = normalized in SENSITIVE_KEYS or any(
                normalized.endswith(f"_{secret}") for secret in SENSITIVE_KEYS
            )
            if is_sensitive and not is_reference:
                raise ValueError(f"Sensitive artifact field is forbidden: {path}.{key}")
            reject_sensitive_data(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_sensitive_data(item, f"{path}[{index}]")


def stable_hash(payload):
    serialized = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ArtifactDependencySnapshot:
    prompt_refs: tuple[dict[str, Any], ...] = ()
    tool_bindings: tuple[dict[str, Any], ...] = ()
    policy_refs: tuple[dict[str, Any], ...] = ()
    capabilities: tuple[str, ...] = ()
    model_binding: dict[str, Any] = field(default_factory=dict)
    memory_policy_ref: str | None = None
    governance_refs: tuple[dict[str, Any], ...] = ()

    def __post_init__(self):
        reject_sensitive_data(self.to_dict())

    def to_dict(self):
        return {
            "prompt_refs": [dict(item) for item in self.prompt_refs],
            "tool_bindings": [dict(item) for item in self.tool_bindings],
            "policy_refs": [dict(item) for item in self.policy_refs],
            "capabilities": list(self.capabilities),
            "model_binding": dict(self.model_binding),
            "memory_policy_ref": self.memory_policy_ref,
            "governance_refs": [dict(item) for item in self.governance_refs],
        }


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
    artifact_hash: str = ""
    graph_ir_version: str = "agent-graph-ir/v1"

    def __post_init__(self):
        for name in ("artifact_id", "agent_id", "agent_version", "graph_hash", "compiler_version"):
            if not getattr(self, name):
                raise ValueError(f"{name} is required")
        if self.status not in AgentLifecycleStatus.ALL:
            raise ValueError(f"Unsupported artifact status: {self.status}")
        reject_sensitive_data(self.dependencies)
        expected = stable_hash(self.hash_content())
        if self.artifact_hash and self.artifact_hash != expected:
            raise ValueError("Compiled artifact hash does not match content")
        if not self.artifact_hash:
            object.__setattr__(self, "artifact_hash", expected)

    def hash_content(self):
        return {
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "graph_ir_hash": self.graph_hash,
            "graph_ir_version": self.graph_ir_version,
            "compiler_version": self.compiler_version,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_ir(cls, graph_ir, compiler_version, dependencies=None):
        graph_hash = graph_ir.stable_hash()
        dependencies = dict(dependencies or {})
        content = {
            "agent_id": graph_ir.agent_id, "agent_version": graph_ir.version,
            "graph_ir_hash": graph_hash,
            "graph_ir_version": getattr(graph_ir, "schema_version", "agent-graph-ir/v1"),
            "compiler_version": compiler_version, "dependencies": dependencies,
        }
        artifact_hash = stable_hash(content)
        return cls(
            artifact_id=f"{graph_ir.agent_id}:{graph_ir.version}:{artifact_hash[:12]}",
            agent_id=graph_ir.agent_id,
            agent_version=graph_ir.version,
            graph_hash=graph_hash,
            compiler_version=compiler_version,
            graph_ir=graph_ir,
            dependencies=dependencies,
            artifact_hash=artifact_hash,
            graph_ir_version=content["graph_ir_version"],
        )
