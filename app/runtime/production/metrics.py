from collections import defaultdict
from threading import RLock

from app.runtime.governance.events import RuntimeEvent


class AgentMetricsCollector:
    """Backend-neutral RuntimeEvent projection for operational metrics."""

    def __init__(self):
        self._metrics = defaultdict(lambda: defaultdict(float))
        self._started = {}
        self._completed = set()
        self._lock = RLock()

    def handle(self, event: RuntimeEvent):
        if not isinstance(event, RuntimeEvent):
            raise TypeError("event must be RuntimeEvent")
        with self._lock:
            values = self._metrics[event.agent_id]
            if event.event_type in {"execution.started", "graph.started"}:
                key = (event.agent_id, event.execution_id)
                if key not in self._started:
                    self._started[key] = event.timestamp
                    values["execution_total"] += 1
            elif event.event_type in {"execution.completed", "graph.completed"}:
                self._complete(event, values, "success_total")
            elif event.event_type in {"execution.failed", "graph.failed"}:
                self._complete(event, values, "failure_total")
            elif event.event_type == "agent.authorization.denied":
                values["authorization_denied"] += 1
            elif event.event_type == "approval.requested":
                values["approval_required"] += 1
            elif event.event_type == "agent.context.projected" and event.status == "blocked":
                values["context_blocked"] += 1
            values["token_usage"] += self._number(event.payload.get("token_usage"))
            values["tool_calls"] += self._number(event.payload.get("tool_calls"))
            values["memory_reads"] += self._number(event.payload.get("memory_reads"))

    def snapshot(self, agent_id: str) -> dict[str, float]:
        with self._lock:
            values = dict(self._metrics.get(agent_id, {}))
            completed = values.get("success_total", 0) + values.get("failure_total", 0)
            values["average_latency"] = (
                values.get("latency_total", 0) / completed if completed else 0
            )
            values.pop("latency_total", None)
            for name in (
                "execution_total", "success_total", "failure_total",
                "authorization_denied", "approval_required", "context_blocked",
                "token_usage", "tool_calls", "memory_reads",
            ):
                values.setdefault(name, 0)
            return values

    def _record_latency(self, event, values):
        started = self._started.pop((event.agent_id, event.execution_id), None)
        if started is not None:
            values["latency_total"] += max(
                0.0, (event.timestamp - started).total_seconds()
            )

    def _complete(self, event, values, metric):
        key = (event.agent_id, event.execution_id)
        if key in self._completed:
            return
        self._completed.add(key)
        values[metric] += 1
        self._record_latency(event, values)

    @staticmethod
    def _number(value):
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0
