"""Policy-specific projection of an already isolated Context Envelope."""

from app.runtime.multi_agent.context import AgentContextEnvelope
from app.runtime.multi_agent.validation import AgentContractValidator
from app.runtime.governance.agent.models import ContextGuardResult


class AgentContextGuard:
    def __init__(self, validator=None):
        self.validator = validator or AgentContractValidator()

    def guard(self, envelope, policy):
        if envelope is None:
            return ContextGuardResult(envelope=None)
        if not isinstance(envelope, AgentContextEnvelope):
            raise TypeError("context must be AgentContextEnvelope")
        self.validator.validate(envelope)
        allowed = set(policy.allowed_context_fields)
        removed = []

        def project(section, values):
            output = {}
            for key, value in values.items():
                if key in allowed or f"{section}.{key}" in allowed:
                    output[key] = value
                else:
                    removed.append(f"{section}.{key}")
            return output

        upstream = (
            envelope.upstream_results if "upstream_results" in allowed else {}
        )
        if envelope.upstream_results and not upstream:
            removed.append("upstream_results")
        evidence = envelope.evidence_refs if "evidence_refs" in allowed else ()
        if envelope.evidence_refs and not evidence:
            removed.append("evidence_refs")
        provenance = envelope.provenance if "provenance" in allowed else ()
        if envelope.provenance and not provenance:
            removed.append("provenance")
        safe = AgentContextEnvelope(
            shared_facts=project("shared_facts", envelope.shared_facts),
            upstream_results=upstream,
            evidence_refs=evidence,
            task_context=project("task_context", envelope.task_context),
            correlation=envelope.correlation,
            provenance=provenance,
        )
        self.validator.validate(safe)
        return ContextGuardResult(
            envelope=safe,
            removed_fields=tuple(sorted(set(removed))),
        )
