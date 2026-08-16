"""Optimization governance (Phase 17.6).

Controlled autonomous optimization: LOW risk auto-approves, MEDIUM risk requires
human approval, HIGH risk (policy / permission / tool / action) is forbidden for
auto-optimization.  Fail-closed: an ungoverned proposal requires approval.
"""

from app.platform.intelligence.errors import GovernanceDeniedError
from app.platform.intelligence.optimization.proposal import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    TARGET_POLICY,
)

DECISION_AUTO_APPROVE = "AUTO_APPROVE"
DECISION_REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
DECISION_FORBIDDEN = "FORBIDDEN"


class OptimizationGovernance:

    def __init__(self, policies=None):
        self._policies = list(policies or [])

    def policy_for(self, target_type, risk_level):
        for policy in self._policies:
            if policy.target_type == target_type and policy.risk_level == risk_level:
                return policy
        return None

    def evaluate(self, proposal) -> str:
        policy = self.policy_for(proposal.target_type, proposal.risk_level)
        if policy is not None:
            if policy.forbidden:
                return DECISION_FORBIDDEN
            return DECISION_REQUIRE_APPROVAL if policy.require_approval \
                else DECISION_AUTO_APPROVE
        # default governance (fail-closed)
        if proposal.risk_level == RISK_HIGH and proposal.target_type == TARGET_POLICY:
            return DECISION_FORBIDDEN
        if proposal.risk_level == RISK_LOW:
            return DECISION_AUTO_APPROVE
        return DECISION_REQUIRE_APPROVAL

    def authorize(self, proposal, approved=False):
        decision = self.evaluate(proposal)
        if decision == DECISION_FORBIDDEN:
            raise GovernanceDeniedError(
                f"proposal {proposal.proposal_id!r} targets a forbidden area "
                f"({proposal.target_type} @ {proposal.risk_level})"
            )
        if decision == DECISION_REQUIRE_APPROVAL and not approved:
            raise GovernanceDeniedError(
                f"proposal {proposal.proposal_id!r} requires approval"
            )
        return decision


__all__ = [
    "OptimizationGovernance",
    "DECISION_AUTO_APPROVE",
    "DECISION_REQUIRE_APPROVAL",
    "DECISION_FORBIDDEN",
]
