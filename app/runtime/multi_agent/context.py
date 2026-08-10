"""Serializable context envelope; projection is implemented separately."""

from dataclasses import dataclass, field
from typing import Any

from app.runtime.multi_agent.models import (
    AgentProvenance,
    ContextCorrelation,
    EvidenceReference,
)
from app.runtime.multi_agent.validation import validate_transfer_value


@dataclass(frozen=True)
class AgentContextEnvelope:
    shared_facts: dict[str, Any]
    upstream_results: dict[str, Any]
    evidence_refs: tuple[EvidenceReference, ...]
    task_context: dict[str, Any]
    correlation: ContextCorrelation
    provenance: tuple[AgentProvenance, ...] = ()
    schema_version: str = "agent-context.v1"

    def __post_init__(self):
        if self.schema_version != "agent-context.v1":
            raise ValueError(f"Unsupported context schema: {self.schema_version}")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        for name in ("shared_facts", "upstream_results", "task_context"):
            if not isinstance(getattr(self, name), dict):
                raise TypeError(f"{name} must be a dict")
        validate_transfer_value(self.to_dict(), "AgentContextEnvelope")

    def to_dict(self):
        return {
            "shared_facts": validate_transfer_value(
                self.shared_facts, "shared_facts"
            ),
            "upstream_results": validate_transfer_value(
                self.upstream_results, "upstream_results"
            ),
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "task_context": validate_transfer_value(
                self.task_context, "task_context"
            ),
            "correlation": self.correlation.to_dict(),
            "provenance": [item.to_dict() for item in self.provenance],
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, payload):
        data = dict(payload)
        data["evidence_refs"] = tuple(
            EvidenceReference.from_dict(item)
            for item in data.get("evidence_refs", [])
        )
        data["correlation"] = ContextCorrelation.from_dict(data["correlation"])
        data["provenance"] = tuple(
            AgentProvenance.from_dict(item)
            for item in data.get("provenance", [])
        )
        return cls(**data)
