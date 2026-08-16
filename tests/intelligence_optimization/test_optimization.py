"""Phase 17.2 Optimization Engine tests."""

from app.platform.intelligence.evaluation import AgentEvaluation
from app.platform.intelligence.optimization import (
    OptimizationGenerator,
    PatternDetector,
)


def _evaluation(**metrics):
    data = {"failure_rate": 0.0, "avg_cost": 0.0}
    data.update(metrics)
    return AgentEvaluation(
        evaluation_id="e1", agent_id="commerce_agent", agent_version="1.0",
        evaluation_type="execution_quality", score=0.5, metrics=data)


def test_detector_flags_performance_issue():
    detector = PatternDetector(failure_rate_threshold=0.2)
    issues = detector.detect(_evaluation(failure_rate=0.35))
    assert any(i.issue_type == "performance" for i in issues)


def test_detector_flags_cost_issue():
    detector = PatternDetector(cost_threshold=1.0)
    issues = detector.detect(_evaluation(avg_cost=5.0))
    assert any(i.issue_type == "cost" for i in issues)


def test_detector_no_issues_when_healthy():
    detector = PatternDetector()
    issues = detector.detect(_evaluation(failure_rate=0.01, avg_cost=0.1))
    assert issues == []


def test_generator_creates_proposal_with_evidence():
    detector = PatternDetector()
    generator = OptimizationGenerator()
    issue = detector.detect(_evaluation(failure_rate=0.4))[0]
    proposal = generator.generate(issue, target_id="store_diagnosis", current_version="1.0")
    assert proposal.target_type == "SKILL"
    assert proposal.risk_level == "HIGH"
    assert proposal.evidence["failure_rate"] == 0.4


def test_generator_llm_only_suggests_text():
    def llm(base):
        return "降低 failure rate：调整 skill 阈值"

    generator = OptimizationGenerator(llm=llm)
    detector = PatternDetector()
    issue = detector.detect(_evaluation(avg_cost=5.0))[0]
    proposal = generator.generate(issue, target_id="prompt_v1", current_version="1.0")
    assert proposal.suggested_change == "降低 failure rate：调整 skill 阈值"
    assert proposal.risk_level == "LOW"
