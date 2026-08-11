import pytest

from app.runtime.production import (
    AgentCapacityManager, AgentExecutionQuota, QuotaUsage,
)


def quota(**overrides):
    values = {
        "agent_id": "sales_agent",
        "max_parallel_execution": 2,
        "max_execution_time": 30,
        "max_tool_calls": 5,
        "max_token_usage": 1000,
        "policy_version": "quota-v2",
    }
    values.update(overrides)
    return AgentExecutionQuota(**values)


def test_atomic_capacity_acquisition_and_release():
    manager = AgentCapacityManager({"sales_agent": quota()})
    assert manager.acquire("sales_agent", "one").allowed
    assert manager.acquire("sales_agent", "two").allowed
    denied = manager.acquire("sales_agent", "three")
    assert not denied.allowed
    assert denied.reason == "concurrency_limit"
    manager.release("sales_agent", "one")
    assert manager.acquire("sales_agent", "three").allowed


def test_same_execution_acquire_is_idempotent():
    manager = AgentCapacityManager({"sales_agent": quota(max_parallel_execution=1)})
    manager.acquire("sales_agent", "same")
    decision = manager.acquire("sales_agent", "same")
    assert decision.allowed
    assert decision.reason == "already_acquired"
    assert manager.active_count("sales_agent") == 1


@pytest.mark.parametrize(
    ("usage", "reason"),
    [
        (QuotaUsage(execution_time=31), "execution_time_limit"),
        (QuotaUsage(tool_calls=6), "tool_call_limit"),
        (QuotaUsage(token_usage=1001), "token_usage_limit"),
    ],
)
def test_resource_limits_reject_overage(usage, reason):
    manager = AgentCapacityManager({"sales_agent": quota()})
    decision = manager.check_usage("sales_agent", usage)
    assert not decision.allowed
    assert decision.reason == reason


@pytest.mark.parametrize(
    "usage",
    [
        QuotaUsage(execution_time=30),
        QuotaUsage(tool_calls=5),
        QuotaUsage(token_usage=1000),
    ],
)
def test_resource_limits_are_inclusive(usage):
    manager = AgentCapacityManager({"sales_agent": quota()})
    assert manager.check_usage("sales_agent", usage).allowed


@pytest.mark.parametrize(
    "override",
    [
        {"max_parallel_execution": 0},
        {"max_execution_time": 0},
        {"max_tool_calls": -1},
        {"max_token_usage": -1},
    ],
)
def test_invalid_quota_is_rejected(override):
    with pytest.raises(ValueError):
        quota(**override)


def test_quota_decision_contains_replayable_policy_snapshot():
    manager = AgentCapacityManager({"sales_agent": quota()})
    decision = manager.acquire("sales_agent", "execution")
    assert decision.quota_snapshot == quota().snapshot()
    assert decision.quota_snapshot["policy_version"] == "quota-v2"
