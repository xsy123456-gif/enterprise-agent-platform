"""Phase 17.6 Governance tests."""

import pytest

from app.platform.intelligence.errors import GovernanceDeniedError
from app.platform.intelligence.governance import OptimizationGovernance
from app.platform.intelligence.optimization import OptimizationProposal


def _proposal(risk_level, target_type):
    return OptimizationProposal(
        proposal_id="p1", target_type=target_type, target_id="t1",
        current_version="1.0", suggested_change="x", risk_level=risk_level)


def test_low_risk_auto_approve():
    governance = OptimizationGovernance()
    proposal = _proposal("LOW", "PROMPT")
    assert governance.evaluate(proposal) == "AUTO_APPROVE"
    governance.authorize(proposal)  # no raise


def test_medium_risk_requires_approval():
    governance = OptimizationGovernance()
    proposal = _proposal("MEDIUM", "SKILL")
    assert governance.evaluate(proposal) == "REQUIRE_APPROVAL"
    with pytest.raises(GovernanceDeniedError):
        governance.authorize(proposal, approved=False)
    governance.authorize(proposal, approved=True)


def test_high_risk_policy_forbidden():
    governance = OptimizationGovernance()
    proposal = _proposal("HIGH", "POLICY")
    assert governance.evaluate(proposal) == "FORBIDDEN"
    with pytest.raises(GovernanceDeniedError):
        governance.authorize(proposal, approved=True)  # even approved -> forbidden


def test_explicit_policy_overrides():
    from app.platform.intelligence.governance import OptimizationPolicy
    governance = OptimizationGovernance([
        OptimizationPolicy(policy_id="p1", target_type="PROMPT", risk_level="LOW",
                           require_approval=True, forbidden=False)])
    proposal = _proposal("LOW", "PROMPT")
    assert governance.evaluate(proposal) == "REQUIRE_APPROVAL"
