from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def canonical_json(payload):
    try:
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise ValueError("Backend runtime_definition must be JSON serializable") from error


@dataclass(frozen=True)
class BackendArtifact:
    artifact_id: str
    agent_id: str
    agent_version: str
    backend_type: str
    backend_version: str
    compiler_version: str
    graph_ir_hash: str
    artifact_hash: str
    runtime_definition: dict[str, Any]
    dependencies: dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)

    def __post_init__(self):
        required = (
            "artifact_id", "agent_id", "agent_version", "backend_type",
            "backend_version", "compiler_version", "graph_ir_hash", "artifact_hash",
        )
        for name in required:
            if not isinstance(getattr(self, name), str) or not getattr(self, name):
                raise ValueError(f"{name} is required")
        if not isinstance(self.runtime_definition, dict):
            raise ValueError("runtime_definition must be a mapping")
        canonical_json(self.runtime_definition)
        canonical_json(self.dependencies)

    @classmethod
    def create(cls, *, agent_id, agent_version, backend_type, backend_version,
               compiler_version, graph_ir_hash, runtime_definition, dependencies=None):
        hash_payload = {
            "agent_id": agent_id,
            "agent_version": agent_version,
            "backend_type": backend_type,
            "backend_version": backend_version,
            "compiler_version": compiler_version,
            "graph_ir_hash": graph_ir_hash,
            "runtime_definition": runtime_definition,
            "dependencies": dict(dependencies or {}),
        }
        artifact_hash = hashlib.sha256(
            canonical_json(hash_payload).encode("utf-8")
        ).hexdigest()
        return cls(
            artifact_id=(
                f"{agent_id}:{agent_version}:{backend_type}:{artifact_hash[:12]}"
            ),
            agent_id=agent_id,
            agent_version=agent_version,
            backend_type=backend_type,
            backend_version=backend_version,
            compiler_version=compiler_version,
            graph_ir_hash=graph_ir_hash,
            artifact_hash=artifact_hash,
            runtime_definition=dict(runtime_definition),
            dependencies=dict(dependencies or {}),
        )

    def to_dict(self):
        return {
            "artifact_id": self.artifact_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "backend_type": self.backend_type,
            "backend_version": self.backend_version,
            "compiler_version": self.compiler_version,
            "graph_ir_hash": self.graph_ir_hash,
            "artifact_hash": self.artifact_hash,
            "runtime_definition": dict(self.runtime_definition),
            "dependencies": dict(self.dependencies),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
