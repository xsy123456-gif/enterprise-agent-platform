"""Serializable envelope and platform-owned context projection boundary."""

from dataclasses import dataclass, field
from typing import Any

from app.runtime.multi_agent.models import (
    AgentProvenance,
    ContextCorrelation,
    EvidenceReference,
)
from app.runtime.multi_agent.validation import (
    AgentContractValidator,
    RUNTIME_CONTEXT_KEYS,
    is_sensitive_key,
    normalized_key,
    validate_transfer_value,
)


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


@dataclass(frozen=True)
class ContextTransferPolicy:
    """Field propagation policy; it is not an authorization decision."""

    allowed_shared_fields: frozenset[str] | None = None
    denied_fields: frozenset[str] = field(
        default_factory=lambda: frozenset(RUNTIME_CONTEXT_KEYS)
    )
    max_payload_bytes: int = 64 * 1024

    def __post_init__(self):
        if self.allowed_shared_fields is not None:
            object.__setattr__(
                self, "allowed_shared_fields",
                frozenset(normalized_key(item) for item in self.allowed_shared_fields),
            )
        object.__setattr__(
            self, "denied_fields",
            frozenset(normalized_key(item) for item in self.denied_fields),
        )
        if self.max_payload_bytes <= 0:
            raise ValueError("max_payload_bytes must be positive")


class ContextProjector:
    """Projects a public Agent result into bounded downstream context."""

    def __init__(self, policy=None, validator=None):
        self.policy = policy or ContextTransferPolicy()
        self.validator = validator or AgentContractValidator(
            max_payload_bytes=self.policy.max_payload_bytes
        )

    def project(
        self,
        result,
        *,
        trace_id,
        invocation_id,
        shared_facts=None,
        task_context=None,
        source_message_id=None,
    ):
        from app.runtime.multi_agent.contracts import AgentExecutionResult

        if not isinstance(result, AgentExecutionResult):
            raise TypeError("result must be AgentExecutionResult")
        self.validator.validate(result)
        facts = self._sanitize_mapping(shared_facts or {}, apply_allowlist=True)
        task = self._sanitize_mapping(task_context or {})
        output = self._sanitize_value(result.output, "output")
        findings = self._sanitize_value(list(result.findings), "findings")
        provenance = AgentProvenance(
            source_agent_id=result.agent_id,
            source_agent_version=result.agent_version,
            source_artifact_id=result.artifact_id,
            source_artifact_hash=result.artifact_hash,
            source_agent_execution_id=result.agent_execution_id,
            source_message_id=source_message_id,
        )
        envelope = AgentContextEnvelope(
            shared_facts=facts,
            upstream_results={
                result.agent_id: {
                    "output": output,
                    "findings": findings,
                    "confidence": result.confidence,
                    "status": result.status.value,
                }
            },
            evidence_refs=result.evidence,
            task_context=task,
            correlation=ContextCorrelation(
                execution_id=result.execution_id,
                trace_id=trace_id,
                parent_agent_execution_id=result.agent_execution_id,
                invocation_id=invocation_id,
                source_message_id=source_message_id,
            ),
            provenance=(provenance,),
        )
        return self.validator.validate(envelope)

    def _sanitize_mapping(self, value, apply_allowlist=False):
        if not isinstance(value, dict):
            raise TypeError("Projected context fields must be dicts")
        projected = {}
        for key, item in value.items():
            normalized = normalized_key(key)
            if normalized in self.policy.denied_fields:
                continue
            if apply_allowlist and self.policy.allowed_shared_fields is not None:
                if normalized not in self.policy.allowed_shared_fields:
                    continue
            if is_sensitive_key(normalized):
                raise ValueError(f"Sensitive context field is forbidden: {key}")
            projected[str(key)] = self._sanitize_value(item, str(key))
        return projected

    def _sanitize_value(self, value, path):
        if isinstance(value, dict):
            return self._sanitize_mapping(value)
        if isinstance(value, (list, tuple)):
            return [
                self._sanitize_value(item, f"{path}[{index}]")
                for index, item in enumerate(value)
            ]
        return validate_transfer_value(value, path)
