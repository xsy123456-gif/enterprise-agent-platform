"""Phase 17.7 Hardening + Agent Optimization E2E."""

import pytest

from app.platform.intelligence.audit import (
    IntelligenceAuditLogger,
    OP_OPTIMIZATION_APPROVED,
    OP_OPTIMIZATION_CREATED,
    OP_VERSION_RELEASED,
)
from app.platform.intelligence.errors import GovernanceDeniedError
from app.platform.intelligence.evaluation import EvaluationEngine, ExecutionSample
from app.platform.intelligence.experiment import (
    AgentExperiment,
    ExperimentEvaluator,
)
from app.platform.intelligence.governance import OptimizationGovernance
from app.platform.intelligence.improvement import (
    AgentImprovementRequest,
    ImprovementApproval,
    ImprovementLifecycle,
)
from app.platform.intelligence.optimization import (
    OptimizationGenerator,
    PatternDetector,
)


# ── Agent Optimization E2E ─────────────────────────────────

def test_agent_optimization_e2e():
    audit = IntelligenceAuditLogger()
    # 1. evaluate v1.0 execution data
    engine = EvaluationEngine()
    samples = [ExecutionSample(success=(i % 10 != 0), latency_ms=100.0,
                               cost=0.5) for i in range(100)]
    evaluation = engine.evaluate_execution_quality(
        "e1", "commerce_agent", "1.0", samples)
    assert evaluation.metrics["failure_rate"] == pytest.approx(0.1)

    # 2. detect + generate optimization proposal
    detector = PatternDetector(failure_rate_threshold=0.05)
    issues = detector.detect(evaluation)
    assert issues  # failure rate 0.1 > 0.05
    generator = OptimizationGenerator()
    proposal = generator.generate(issues[0], target_id="store_diagnosis",
                                  current_version="1.0")
    audit.record("commerce_agent", "OptimizationCreated",
                 proposal_id=proposal.proposal_id)

    # 3. governance: MEDIUM risk (failure rate 0.1 <= 0.3) requires approval
    governance = OptimizationGovernance()
    assert governance.evaluate(proposal) == "REQUIRE_APPROVAL"
    with pytest.raises(GovernanceDeniedError):
        governance.authorize(proposal, approved=False)

    # 4. improvement lifecycle -> approved -> released
    lifecycle = ImprovementLifecycle()
    request = AgentImprovementRequest(
        request_id="r1", proposal_id=proposal.proposal_id,
        target_agent="commerce_agent", change_type="skill_config")
    lifecycle.create(request)
    for state in ("VALIDATED", "REVIEWING"):
        lifecycle.transition("r1", state)
    approval = ImprovementApproval(lifecycle)
    approval.approve(request, "lead")
    audit.record("commerce_agent", "OptimizationApproved",
                 proposal_id=proposal.proposal_id)
    for state in ("IMPLEMENTING", "TESTING"):
        lifecycle.transition("r1", state)

    # 5. experiment decides release
    experiment = AgentExperiment(
        experiment_id="exp1", control_version="1.0", candidate_version="1.1",
        strategy="AB_TEST", traffic_ratio=0.1)
    audit.record("commerce_agent", "ExperimentStarted",
                 proposal_id=proposal.proposal_id)
    decision = ExperimentEvaluator().decide(
        control_quality=0.9, candidate_quality=0.95, risk=0.1)
    assert decision is True

    # 6. release v1.1
    lifecycle.release("r1")
    assert lifecycle.status("r1") == "RELEASED"
    audit.record("commerce_agent", "VersionReleased",
                 proposal_id=proposal.proposal_id)

    ops = {r.operation for r in audit.list()}
    assert ops == {"OptimizationCreated", "OptimizationApproved",
                   "ExperimentStarted", "VersionReleased"}


# ── Security hardening ─────────────────────────────────────

def test_optimization_bypass_blocked():
    governance = OptimizationGovernance()
    from app.platform.intelligence.optimization import OptimizationProposal
    proposal = OptimizationProposal(
        proposal_id="p1", target_type="POLICY", target_id="action_policy",
        risk_level="HIGH", suggested_change="grant agent admin")
    with pytest.raises(GovernanceDeniedError):
        governance.authorize(proposal, approved=True)


def test_unauthorized_self_approval_blocked():
    lifecycle = ImprovementLifecycle()
    request = AgentImprovementRequest(
        request_id="r1", proposal_id="p1", target_agent="commerce_agent",
        change_type="skill_config")
    lifecycle.create(request)
    from app.platform.intelligence.improvement import ImprovementApproval
    approval = ImprovementApproval(lifecycle)
    from app.platform.intelligence.errors import ImprovementError
    with pytest.raises(ImprovementError):
        approval.approve(request, "agent_itself")  # not REVIEWING -> blocked


def test_evaluation_manipulation_detected():
    # a fabricated score outside [0,1] is rejected at construction
    from app.platform.intelligence.evaluation import AgentEvaluation
    with pytest.raises(ValueError):
        AgentEvaluation(evaluation_id="e", agent_id="a", agent_version="1.0",
                        evaluation_type="execution_quality", score=2.0)


# ── Audit / replay ─────────────────────────────────────────

def test_audit_never_contains_secret():
    audit = IntelligenceAuditLogger()
    record = audit.record("commerce_agent", "VersionReleased", proposal_id="p1",
                          trace_id="t1")
    for forbidden in ("secret", "credential", "token", "password", "private"):
        assert forbidden not in record.to_dict()
        assert not hasattr(record, forbidden)


def test_replay_captures_full_chain():
    # original version -> evaluation -> proposal -> new version -> approval
    engine = EvaluationEngine()
    evaluation = engine.evaluate_execution_quality(
        "e1", "commerce_agent", "1.0", [ExecutionSample(success=False)])
    detector = PatternDetector(failure_rate_threshold=0.0)
    proposal = OptimizationGenerator().generate(
        detector.detect(evaluation)[0], target_id="s", current_version="1.0")
    assert evaluation.agent_version == "1.0"
    assert proposal.current_version == "1.0"
    assert proposal.proposal_id
