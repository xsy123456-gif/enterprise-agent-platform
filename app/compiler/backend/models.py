from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any
from app.artifacts.models import AgentLifecycleStatus, reject_sensitive_data


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
    status: str = AgentLifecycleStatus.ACTIVE

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
        reject_sensitive_data(self.runtime_definition)
        reject_sensitive_data(self.dependencies)
        if self.status not in AgentLifecycleStatus.ALL:
            raise ValueError(f"Unsupported artifact status: {self.status}")
        if self.artifact_hash != self.calculate_hash():
            raise ValueError("Backend artifact hash does not match content")

    def hash_content(self):
        return {
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "backend_type": self.backend_type,
            "backend_version": self.backend_version,
            "compiler_version": self.compiler_version,
            "graph_ir_hash": self.graph_ir_hash,
            "runtime_definition": self.runtime_definition,
            "dependencies": self.dependencies,
        }

    def calculate_hash(self):
        return hashlib.sha256(
            canonical_json(self.hash_content()).encode("utf-8")
        ).hexdigest()

    def verify(self, backend_type=None, production=True):
        if backend_type is not None and self.backend_type != backend_type:
            raise ValueError(
                f"Artifact backend mismatch: {self.backend_type} != {backend_type}"
            )
        if self.artifact_hash != self.calculate_hash():
            raise ValueError("Backend artifact hash verification failed")
        executable = (
            {AgentLifecycleStatus.ACTIVE}
            if production else
            {AgentLifecycleStatus.COMPILED, AgentLifecycleStatus.PUBLISHED,
             AgentLifecycleStatus.ACTIVE}
        )
        if self.status not in executable:
            raise ValueError(f"Artifact is not executable: {self.status}")
        return True

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
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, payload):
        return cls(**dict(payload))
