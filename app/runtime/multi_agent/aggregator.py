"""Fan-in aggregation of public Agent results only."""

from dataclasses import dataclass, field
from typing import Any

from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.multi_agent.models import (
    AgentProvenance,
    AgentResultStatus,
    EvidenceReference,
)
from app.runtime.multi_agent.validation import validate_transfer_value


@dataclass(frozen=True)
class AggregatedAgentResult:
    execution_id: str
    status: str
    findings: tuple[dict[str, Any], ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    provenance: tuple[AgentProvenance, ...] = ()
    agent_sources: tuple[dict[str, str], ...] = ()
    outputs: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    failed_agents: tuple[str, ...] = ()
    skipped_agents: tuple[str, ...] = ()
    schema_version: str = "aggregated-agent-result.v1"

    def __post_init__(self):
        if not self.execution_id or not self.status:
            raise ValueError("execution_id and status are required")
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "provenance", tuple(self.provenance))
        object.__setattr__(self, "agent_sources", tuple(self.agent_sources))
        object.__setattr__(self, "failed_agents", tuple(self.failed_agents))
        object.__setattr__(self, "skipped_agents", tuple(self.skipped_agents))
        validate_transfer_value(self.to_dict(), "AggregatedAgentResult")

    def to_dict(self):
        return {
            "execution_id": self.execution_id,
            "status": self.status,
            "findings": list(self.findings),
            "evidence": [item.to_dict() for item in self.evidence],
            "provenance": [item.to_dict() for item in self.provenance],
            "agent_sources": list(self.agent_sources),
            "outputs": dict(self.outputs),
            "confidence": self.confidence,
            "failed_agents": list(self.failed_agents),
            "skipped_agents": list(self.skipped_agents),
            "schema_version": self.schema_version,
        }


class AgentResultAggregator:
    """Joins results while excluding Runtime, Permission and Memory state."""

    def aggregate(self, execution_id, results, *, skipped_agents=()):
        results = tuple(results)
        if any(not isinstance(item, AgentExecutionResult) for item in results):
            raise TypeError("Aggregator accepts AgentExecutionResult only")
        failed = tuple(
            item.agent_id for item in results
            if item.status in {
                AgentResultStatus.FAILED,
                AgentResultStatus.DENIED,
                AgentResultStatus.CANCELLED,
            }
        )
        skipped = tuple(skipped_agents)
        successful = tuple(
            item for item in results if item.status is AgentResultStatus.COMPLETED
        )
        if failed and not successful:
            status = "failed"
        elif failed or skipped:
            status = "partial_failed"
        else:
            status = "completed"
        findings = tuple(
            finding for item in results for finding in item.findings
        )
        evidence = self._unique_evidence(item.evidence for item in results)
        provenance = tuple(
            provenance for item in results for provenance in (item.provenance or ())
        )
        agent_sources = tuple({
            "agent_id": item.agent_id,
            "agent_version": item.agent_version,
            "artifact_id": item.artifact_id,
            "artifact_hash": item.artifact_hash,
        } for item in results)
        outputs = {
            item.agent_id: item.output for item in results
            if item.status not in {
                AgentResultStatus.FAILED,
                AgentResultStatus.DENIED,
                AgentResultStatus.CANCELLED,
            }
        }
        confidences = [item.confidence for item in successful if item.confidence is not None]
        return AggregatedAgentResult(
            execution_id=execution_id,
            status=status,
            findings=findings,
            evidence=evidence,
            provenance=provenance,
            agent_sources=agent_sources,
            outputs=outputs,
            confidence=(sum(confidences) / len(confidences)) if confidences else None,
            failed_agents=failed,
            skipped_agents=skipped,
        )

    @staticmethod
    def _unique_evidence(evidence_groups):
        seen = set()
        output = []
        for group in evidence_groups:
            for evidence in group:
                identity = (evidence.type, evidence.ref, evidence.source)
                if identity not in seen:
                    seen.add(identity)
                    output.append(evidence)
        return tuple(output)
