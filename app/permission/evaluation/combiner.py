"""Effect combination — deterministic ALLOW/DENY resolution."""

from dataclasses import dataclass

from app.permission.evaluation.operators import TruthValue
from app.permission.models.decision import (
    Decision,
    PolicyReference,
    ReasonCode,
)


@dataclass(frozen=True)
class EvaluationResult:
    decision: Decision
    reason_code: ReasonCode
    matched_policy_refs: tuple[PolicyReference, ...] = ()
    policy_set_version: str = ""


def combine(matches, policy_set_version: str) -> EvaluationResult:
    """matches: list[(policy, TruthValue)] for target-applicable active policies.

    Priority (not policy priority): ERROR > explicit DENY > indeterminate DENY
    > explicit ALLOW > indeterminate ALLOW (-> DENY) > no match.
    """
    refs = [PolicyReference(p.policy_id, p.version) for p, _ in matches]

    if any(tv is TruthValue.ERROR for _, tv in matches):
        return EvaluationResult(
            Decision.DENY, ReasonCode.DENY_EVALUATION_ERROR, tuple(refs),
            policy_set_version,
        )

    if any(p.effect == "deny" and tv is TruthValue.TRUE for p, tv in matches):
        matched = tuple(
            PolicyReference(p.policy_id, p.version)
            for p, tv in matches if p.effect == "deny" and tv is TruthValue.TRUE
        )
        return EvaluationResult(
            Decision.DENY, ReasonCode.DENY_EXPLICIT, matched, policy_set_version,
        )

    if any(p.effect == "deny" and tv is TruthValue.UNKNOWN for p, tv in matches):
        matched = tuple(
            PolicyReference(p.policy_id, p.version)
            for p, tv in matches if p.effect == "deny" and tv is TruthValue.UNKNOWN
        )
        return EvaluationResult(
            Decision.DENY, ReasonCode.DENY_INDETERMINATE, matched, policy_set_version,
        )

    if any(p.effect == "allow" and tv is TruthValue.TRUE for p, tv in matches):
        matched = tuple(
            PolicyReference(p.policy_id, p.version)
            for p, tv in matches if p.effect == "allow" and tv is TruthValue.TRUE
        )
        return EvaluationResult(
            Decision.ALLOW, ReasonCode.ALLOWED_POLICY_MATCH, matched, policy_set_version,
        )

    # Only indeterminate ALLOW remains -> fail closed.
    if any(p.effect == "allow" and tv is TruthValue.UNKNOWN for p, tv in matches):
        matched = tuple(
            PolicyReference(p.policy_id, p.version)
            for p, tv in matches if p.effect == "allow" and tv is TruthValue.UNKNOWN
        )
        return EvaluationResult(
            Decision.DENY, ReasonCode.DENY_INDETERMINATE, matched, policy_set_version,
        )

    # No applicable policy matched.
    return EvaluationResult(
        Decision.DENY, ReasonCode.DENY_NO_MATCH, (), policy_set_version,
    )
