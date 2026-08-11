import pytest

from app.runtime.recovery import (
    AgentRetryPolicy,
    BackoffStrategy,
    FailureClassifier,
    FailureType,
    GraphRecoveryPolicy,
    RecoveryAction,
    RetryManager,
)
from tests.runtime.recovery.helpers import result


@pytest.mark.parametrize(("strategy", "retry_number", "expected"), [
    (BackoffStrategy.NONE, 1, 0.0),
    (BackoffStrategy.FIXED, 1, 2.0),
    (BackoffStrategy.FIXED, 3, 2.0),
    (BackoffStrategy.EXPONENTIAL, 1, 2.0),
    (BackoffStrategy.EXPONENTIAL, 3, 8.0),
])
def test_backoff_calculation(strategy, retry_number, expected):
    policy = AgentRetryPolicy(
        max_attempts=4, backoff_strategy=strategy, backoff_seconds=2
    )
    assert policy.delay_for(retry_number) == expected


def failure(code="LLM_TIMEOUT"):
    return FailureClassifier().classify(
        result(status="failed", code=code, retryable=True), "attempt-1"
    )


def test_retry_manager_retries_eligible_failure():
    decision = RetryManager().decide(
        failure(), [object()], AgentRetryPolicy(max_attempts=2)
    )
    assert decision.action is RecoveryAction.RETRY
    assert decision.retry_number == 1


def test_retry_manager_stops_when_attempts_exhausted():
    decision = RetryManager().decide(
        failure(), [object(), object()], AgentRetryPolicy(max_attempts=2)
    )
    assert decision.action is RecoveryAction.STOP


def test_non_retryable_failure_uses_escalation_fallback():
    policy = AgentRetryPolicy(
        max_attempts=3, fallback_strategy=RecoveryAction.ESCALATE
    )
    permission = FailureClassifier().classify(
        result(status="denied", code="PERMISSION_DENIED", category="policy"),
        "attempt-1",
    )
    assert RetryManager().decide(permission, [object()], policy).action is RecoveryAction.ESCALATE


def test_graph_recovery_policy_resolves_per_agent_action():
    policy = GraphRecoveryPolicy(
        failure_strategy={"finance": "RETRY", "risk": "ESCALATE"},
        continue_on_partial_failure=True, max_graph_retry=2,
    )
    assert policy.action_for("finance") is RecoveryAction.RETRY
    assert policy.action_for("risk") is RecoveryAction.ESCALATE
    assert policy.action_for("sales") is RecoveryAction.STOP


def test_retry_policy_rejects_zero_attempts():
    with pytest.raises(ValueError):
        AgentRetryPolicy(max_attempts=0)
