"""Agent budget governance (Phase 15.4).

Tracks spend (daily/monthly buckets) and enforces budget policies.  With
``hard_stop`` a limit breach BLOCKs the execution (BudgetExceededError); without
it the execution is recorded but not blocked.
"""

from app.platform.production.errors import BudgetExceededError
from app.platform.production.observability.cost import CostCollector


def _day(timestamp):
    return (timestamp or "")[:10]


def _month(timestamp):
    return (timestamp or "")[:7]


class BudgetManager:

    def __init__(self, policies=None, cost_collector=None):
        self._policies = {p.agent_id: p for p in (policies or [])}
        self.cost_collector = cost_collector or CostCollector()
        self._daily = {}
        self._monthly = {}

    def record(self, record):
        policy = self._policies.get(record.agent_id)
        if policy is not None:
            day_key = (record.agent_id, record.tenant_id, _day(record.at))
            month_key = (record.agent_id, record.tenant_id, _month(record.at))
            day_spent = self._daily.get(day_key, 0.0) + record.total_cost
            month_spent = self._monthly.get(month_key, 0.0) + record.total_cost
            if policy.hard_stop:
                if policy.daily_limit > 0 and day_spent > policy.daily_limit:
                    raise BudgetExceededError(
                        f"agent {record.agent_id!r} exceeds daily budget "
                        f"({day_spent} > {policy.daily_limit})"
                    )
                if policy.monthly_limit > 0 and month_spent > policy.monthly_limit:
                    raise BudgetExceededError(
                        f"agent {record.agent_id!r} exceeds monthly budget "
                        f"({month_spent} > {policy.monthly_limit})"
                    )
            self._daily[day_key] = day_spent
            self._monthly[month_key] = month_spent
        self.cost_collector.record(record)
        return record

    def daily_spent(self, agent_id, tenant_id=None, day=None):
        total = 0.0
        for (a, t, d), spent in self._daily.items():
            if a != agent_id:
                continue
            if tenant_id is not None and t != tenant_id:
                continue
            if day is not None and d != day:
                continue
            total += spent
        return total

    def total_spent(self, agent_id, tenant_id=None):
        return self.cost_collector.total_for(agent_id, tenant_id=tenant_id)


__all__ = ["BudgetManager"]
