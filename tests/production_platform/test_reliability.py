"""Phase 15.2 Reliability Runtime tests."""

import time

import pytest

from app.platform.production.errors import CircuitOpenError, ExecutionTimeoutError
from app.platform.production.reliability import (
    CircuitBreaker,
    ExecutionTimeoutPolicy,
    RecoveryManager,
    RetryPolicy,
    retry_call,
    run_with_timeout,
)


class _NetworkError(Exception):
    pass


class _PermissionError(Exception):
    pass


def test_retry_retryable_error():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _NetworkError("down")
        return "ok"

    result = retry_call(
        flaky, RetryPolicy(max_retry=3, retryable_errors=(_NetworkError,)),
        sleep=lambda s: None)
    assert result == "ok"
    assert calls["n"] == 3


def test_retry_non_retryable_propagates_immediately():
    def forbidden():
        raise _PermissionError("denied")

    with pytest.raises(_PermissionError):
        retry_call(forbidden, RetryPolicy(max_retry=3,
                                          retryable_errors=(_NetworkError,)),
                   sleep=lambda s: None)


def test_timeout_policy_mapping():
    policy = ExecutionTimeoutPolicy()
    assert policy.for_component("agent") == 300.0
    assert policy.for_component("skill") == 60.0
    assert policy.for_component("tool") == 30.0


def test_run_with_timeout_fires():
    def slow():
        time.sleep(0.2)
        return "late"

    with pytest.raises(ExecutionTimeoutError):
        run_with_timeout(slow, 0.05)


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
    for _ in range(2):
        with pytest.raises(ValueError):
            breaker.call(lambda: (_ for _ in ()).throw(ValueError("x")))
    assert breaker.state == "OPEN"
    with pytest.raises(CircuitOpenError):
        breaker.call(lambda: "ok")


def test_circuit_breaker_recovery_half_open():
    clock = {"t": 0.0}
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=10,
                             clock=lambda: clock["t"])
    with pytest.raises(ValueError):
        breaker.call(lambda: (_ for _ in ()).throw(ValueError("x")))
    assert breaker.state == "OPEN"
    clock["t"] = 20.0
    assert breaker.call(lambda: "ok") == "ok"
    assert breaker.state == "CLOSED"


def test_recovery_fallback_and_escalation():
    manager = RecoveryManager()
    manager.checkpoint("task1", {"step": 1})
    assert manager.restore("task1") == {"step": 1}

    def primary():
        raise RuntimeError("boom")

    def fallback():
        return "fallback result"

    assert manager.run("task1", primary, fallback=fallback) == "fallback result"

    manager.run("task1", primary,
                fallback=lambda: (_ for _ in ()).throw(RuntimeError("x")),
                escalate=lambda: "escalated")
    assert manager.escalations == ["task1"]
