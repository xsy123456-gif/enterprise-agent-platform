import json

import pytest

from app.runtime.recovery import (
    AgentAttemptRecord,
    AttemptStatus,
    FailureClassifier,
    FailureType,
    FailureEscalationEvent,
)
from tests.runtime.recovery.helpers import result


@pytest.mark.parametrize("failure_type", list(FailureType))
def test_failure_types_are_stable(failure_type):
    assert FailureType(failure_type.value) is failure_type


@pytest.mark.parametrize(("code", "category", "status", "expected", "retryable"), [
    ("LLM_TIMEOUT", "runtime", "failed", FailureType.TIMEOUT, True),
    ("NETWORK_UNAVAILABLE", "runtime", "failed", FailureType.TRANSIENT, True),
    ("PERMISSION_DENIED", "policy", "denied", FailureType.POLICY, False),
    ("SCHEMA_INVALID", "validation", "failed", FailureType.VALIDATION, False),
    ("UPSTREAM_FAILED", "dependency", "failed", FailureType.DEPENDENCY, False),
    ("PERMANENT_FAILURE", "runtime", "failed", FailureType.PERMANENT, False),
    ("ODD_FAILURE", "runtime", "failed", FailureType.UNKNOWN, False),
])
def test_failure_classifier(code, category, status, expected, retryable):
    failure = FailureClassifier().classify(
        result(status=status, code=code, category=category), "attempt-1"
    )
    assert failure.failure_type is expected
    assert failure.retryable is retryable
    assert failure.error_code == code


def test_failure_contract_round_trip_contains_no_raw_error_or_stack():
    failure = FailureClassifier().classify(
        result(status="failed", code="LLM_TIMEOUT", retryable=True), "attempt-1"
    )
    payload = json.loads(json.dumps(failure.to_dict()))
    restored = type(failure).from_dict(payload)
    assert restored == failure
    assert "stack" not in payload
    assert "message" not in payload
    assert "response" not in payload


def test_attempt_success_lifecycle_and_round_trip():
    attempt = AgentAttemptRecord("agent-execution-1", 1)
    attempt = attempt.transition(AttemptStatus.RUNNING)
    attempt = attempt.transition(AttemptStatus.SUCCESS)
    assert attempt.started_at and attempt.completed_at
    assert AgentAttemptRecord.from_dict(attempt.to_dict()) == attempt


def test_attempt_failure_records_failure_reference():
    attempt = AgentAttemptRecord("agent-execution-1", 1)
    attempt = attempt.transition("RUNNING").transition("FAILED", "failure-1")
    assert attempt.failure_id == "failure-1"


def test_invalid_attempt_transition_is_rejected():
    with pytest.raises(ValueError, match="Invalid attempt transition"):
        AgentAttemptRecord("agent-execution-1", 1).transition("SUCCESS")


def test_classifier_rejects_successful_result():
    with pytest.raises(ValueError, match="Only failed"):
        FailureClassifier().classify(result(), "attempt-1")


def test_escalation_event_round_trip_contains_references_only():
    failure = FailureClassifier().classify(
        result(status="failed", code="LLM_TIMEOUT"), "attempt-1"
    )
    event = FailureEscalationEvent.from_failure(failure, "retry exhausted")
    assert FailureEscalationEvent.from_dict(event.to_dict()) == event
    assert event.details_ref == failure.details_ref
