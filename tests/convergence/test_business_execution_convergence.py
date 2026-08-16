"""Phase 18.3 Business Action Execution Convergence tests."""

import pytest

from app.platform.business.action import (
    BusinessAction,
    BusinessActionRuntime,
    InMemoryIdempotencyStore,
)


class _RecordingPort:
    def __init__(self):
        self.calls = []

    def execute(self, action, context=None):
        self.calls.append((action.action_type, action.target))


class _RecordingHandler:
    def __init__(self):
        self.calls = []

    def __call__(self, action, context=None):
        self.calls.append((action.action_type, action.target))


def _action(**kwargs):
    return BusinessAction(
        action_id="a1", action_type="UPDATE_AD_BUDGET", target="campaign_A",
        status="APPROVED", **kwargs)


def test_execution_prefers_port_over_handler():
    port = _RecordingPort()
    handler = _RecordingHandler()
    runtime = BusinessActionRuntime(execution_port=port, action_handler=handler)
    runtime.execute(_action())
    assert len(port.calls) == 1
    assert handler.calls == []  # production path does not use the private handler


def test_idempotency_skips_re_dispatch():
    port = _RecordingPort()
    store = InMemoryIdempotencyStore()
    runtime = BusinessActionRuntime(execution_port=port, idempotency_store=store)
    action = _action(idempotency_key="key-1")
    first = runtime.execute(action)
    second = runtime.execute(action)  # same idempotency key
    assert first.status == "SUCCEEDED"
    assert second.status == "SUCCEEDED"
    assert len(port.calls) == 1  # dispatched exactly once


def test_precondition_failed_blocks_execution():
    port = _RecordingPort()
    runtime = BusinessActionRuntime(
        execution_port=port,
        precondition_checker=lambda a, c: (False, "expected 1000, got 1200"),
    )
    action = _action(expected_resource_version="v1")
    from app.platform.business.errors import ActionExecutionError
    with pytest.raises(ActionExecutionError):
        runtime.execute(action)
    assert port.calls == []


def test_precondition_ok_executes():
    port = _RecordingPort()
    runtime = BusinessActionRuntime(
        execution_port=port,
        precondition_checker=lambda a, c: (True, ""),
    )
    result = runtime.execute(_action(expected_resource_version="v1"))
    assert result.status == "SUCCEEDED"
    assert len(port.calls) == 1


def test_no_port_no_handler_raises():
    runtime = BusinessActionRuntime()
    from app.platform.business.errors import ActionExecutionError
    with pytest.raises(ActionExecutionError):
        runtime.execute(_action())
