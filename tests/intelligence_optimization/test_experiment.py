"""Phase 17.4 Experiment Platform tests."""

import pytest

from app.platform.intelligence.experiment import (
    AgentExperiment,
    ExperimentEvaluator,
    TrafficAssignment,
)


def test_shadow_always_routes_to_control():
    experiment = AgentExperiment(
        experiment_id="e1", control_version="1.0", candidate_version="1.1",
        strategy="SHADOW")
    assignment = TrafficAssignment(experiment)
    assert assignment.route("user1") == "control"
    assert assignment.route("user2") == "control"


def test_ab_test_traffic_split():
    experiment = AgentExperiment(
        experiment_id="e1", control_version="1.0", candidate_version="1.1",
        strategy="AB_TEST", traffic_ratio=0.1)
    assignment = TrafficAssignment(experiment)
    routes = {assignment.route(f"user{i}") for i in range(100)}
    assert "candidate" in routes  # some users get candidate
    assert "control" in routes


def test_experiment_decision_requires_improvement_and_low_risk():
    evaluator = ExperimentEvaluator(max_risk=0.3)
    assert evaluator.decide(control_quality=0.7, candidate_quality=0.8,
                            risk=0.1) is True
    assert evaluator.decide(control_quality=0.7, candidate_quality=0.6,
                            risk=0.1) is False  # candidate worse
    assert evaluator.decide(control_quality=0.7, candidate_quality=0.8,
                            risk=0.5) is False  # too risky


def test_experiment_validation():
    with pytest.raises(ValueError):
        AgentExperiment(experiment_id="e", control_version="1.0",
                        candidate_version="1.1", traffic_ratio=1.5)
