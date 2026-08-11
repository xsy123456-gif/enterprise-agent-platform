"""Result identity, provenance, evidence and schema validation."""

from app.runtime.multi_agent.contracts import AgentExecutionResult
from app.runtime.governance.agent.models import ResultValidation, TrustLevel


class AgentResultValidator:
    def validate(self, result, request, node):
        if not isinstance(result, AgentExecutionResult):
            raise TypeError("result must be AgentExecutionResult")
        issues = []
        if result.schema_version != "agent-result.v1":
            issues.append("invalid_schema")
        if result.agent_id != node.agent_id:
            issues.append("invalid_agent_identity")
        if result.artifact_id != node.artifact_id:
            issues.append("invalid_artifact_id")
        if result.artifact_hash != node.artifact_hash:
            issues.append("invalid_artifact_hash")
        if result.execution_id != request.execution_id:
            issues.append("invalid_execution_id")
        if result.agent_execution_id != request.agent_execution_id:
            issues.append("invalid_agent_execution_id")
        if result.provenance is None:
            issues.append("missing_provenance")
        else:
            provenance = result.provenance
            if (
                provenance.source_agent_id != result.agent_id
                or provenance.source_agent_version != result.agent_version
                or provenance.source_artifact_id != result.artifact_id
                or provenance.source_artifact_hash != result.artifact_hash
                or provenance.source_agent_execution_id != result.agent_execution_id
            ):
                issues.append("invalid_provenance")
        if not result.evidence:
            issues.append("missing_evidence")
        elif any(not evidence.ref or not evidence.type for evidence in result.evidence):
            issues.append("invalid_evidence_reference")
        identity_issues = {
            "invalid_schema", "invalid_agent_identity", "invalid_artifact_id",
            "invalid_artifact_hash", "invalid_execution_id",
            "invalid_agent_execution_id", "invalid_provenance",
            "missing_provenance",
        }
        if identity_issues.intersection(issues):
            trust = TrustLevel.UNVERIFIED
        elif issues or not result.evidence:
            trust = TrustLevel.PARTIAL
        else:
            trust = TrustLevel.VERIFIED
        return ResultValidation(
            trust_level=trust,
            issues=tuple(issues),
            agent_id=result.agent_id,
            artifact_hash=result.artifact_hash,
        )
