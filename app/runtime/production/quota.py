from threading import RLock

from .models import AgentExecutionQuota, QuotaDecision, QuotaUsage


class AgentCapacityManager:
    """Atomic in-process capacity gate; storage can be replaced behind this API."""

    def __init__(self, quotas=None, on_decision=None):
        self._quotas = dict(quotas or {})
        self._active: dict[str, set[str]] = {}
        self._lock = RLock()
        self._on_decision = on_decision

    def configure(self, quota: AgentExecutionQuota) -> None:
        self._quotas[quota.agent_id] = quota

    def get_quota(self, agent_id: str) -> AgentExecutionQuota:
        try:
            return self._quotas[agent_id]
        except KeyError as error:
            raise KeyError(f"Execution quota not configured: {agent_id}") from error

    def acquire(
        self,
        agent_id: str,
        execution_id: str,
        expected_usage: QuotaUsage | None = None,
    ) -> QuotaDecision:
        if not execution_id:
            raise ValueError("execution_id is required")
        usage = expected_usage or QuotaUsage()
        with self._lock:
            quota = self.get_quota(agent_id)
            active = self._active.setdefault(agent_id, set())
            if execution_id in active:
                decision = self._decision(True, "already_acquired", quota, len(active))
            else:
                reason = self._limit_reason(quota, usage)
                if reason is None and len(active) >= quota.max_parallel_execution:
                    reason = "concurrency_limit"
                if reason is None:
                    active.add(execution_id)
                    decision = self._decision(True, "allowed", quota, len(active))
                else:
                    decision = self._decision(False, reason, quota, len(active))
        self._notify(agent_id, execution_id, decision)
        return decision

    def check_usage(self, agent_id: str, usage: QuotaUsage) -> QuotaDecision:
        with self._lock:
            quota = self.get_quota(agent_id)
            active_count = len(self._active.get(agent_id, ()))
            reason = self._limit_reason(quota, usage)
            decision = self._decision(
                reason is None, reason or "allowed", quota, active_count
            )
        self._notify(agent_id, None, decision)
        return decision

    def release(self, agent_id: str, execution_id: str) -> None:
        with self._lock:
            self._active.setdefault(agent_id, set()).discard(execution_id)

    def active_count(self, agent_id: str) -> int:
        with self._lock:
            return len(self._active.get(agent_id, ()))

    @staticmethod
    def _limit_reason(quota, usage):
        if usage.execution_time > quota.max_execution_time:
            return "execution_time_limit"
        if usage.tool_calls > quota.max_tool_calls:
            return "tool_call_limit"
        if usage.token_usage > quota.max_token_usage:
            return "token_usage_limit"
        return None

    @staticmethod
    def _decision(allowed, reason, quota, active_count):
        return QuotaDecision(
            allowed=allowed,
            reason=reason,
            quota_snapshot=quota.snapshot(),
            active_executions=active_count,
        )

    def _notify(self, agent_id, execution_id, decision):
        if self._on_decision is not None:
            self._on_decision(agent_id, execution_id, decision)
