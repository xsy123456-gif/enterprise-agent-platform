"""Phase 15.4 Cost Governance tests."""

import pytest

from app.platform.production.errors import BudgetExceededError
from app.platform.production.governance import AgentBudgetPolicy, BudgetManager
from app.platform.production.observability.cost import AgentCostRecord


def _record(execution_id, agent_id, total, at):
    return AgentCostRecord(
        execution_id=execution_id, tenant_id="company_A", agent_id=agent_id,
        llm_cost=total, total_cost=total, at=at)


def test_budget_hard_stop_blocks():
    manager = BudgetManager([AgentBudgetPolicy(
        agent_id="finance_agent", daily_limit=100.0, hard_stop=True)])
    manager.record(_record("e1", "finance_agent", 60.0, "2026-08-16T10:00:00"))
    manager.record(_record("e2", "finance_agent", 30.0, "2026-08-16T11:00:00"))
    with pytest.raises(BudgetExceededError):
        manager.record(_record("e3", "finance_agent", 20.0, "2026-08-16T12:00:00"))


def test_budget_soft_limit_does_not_block():
    manager = BudgetManager([AgentBudgetPolicy(
        agent_id="finance_agent", daily_limit=10.0, hard_stop=False)])
    manager.record(_record("e1", "finance_agent", 60.0, "2026-08-16T10:00:00"))
    assert manager.total_spent("finance_agent") == pytest.approx(60.0)


def test_budget_daily_bucket_isolation():
    manager = BudgetManager([AgentBudgetPolicy(
        agent_id="commerce_agent", daily_limit=50.0, hard_stop=True)])
    manager.record(_record("e1", "commerce_agent", 40.0, "2026-08-15T10:00:00"))
    manager.record(_record("e2", "commerce_agent", 40.0, "2026-08-16T10:00:00"))
    assert manager.daily_spent("commerce_agent", day="2026-08-16") == pytest.approx(40.0)


def test_no_policy_no_block():
    manager = BudgetManager()
    manager.record(_record("e1", "sales_agent", 999.0, "2026-08-16T10:00:00"))
    assert manager.total_spent("sales_agent") == pytest.approx(999.0)
