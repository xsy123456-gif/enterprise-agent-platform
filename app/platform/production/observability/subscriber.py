"""Runtime -> Production Observability bridge (Phase 18.8).

``ProductionObservabilitySubscriber`` consumes Runtime execution events (the
Runtime is the *source*; Production Observability is the *consumer*).  It maps
``execution.*`` events into the existing Trace / Metrics / Cost collectors and
never re-executes business logic, never mutates Runtime state, and never does
permission/business judgment.
"""

from app.platform.production.observability.metrics import (
    AgentMetricSample,
    AgentMetricsCollector,
)
from app.platform.production.observability.trace import (
    COMPONENT_AGENT,
    TRACE_FAILED,
    TRACE_SUCCESS,
    ExecutionSpan,
    TraceCollector,
)

_EXECUTION_HANDLERS = (
    "execution.created", "execution.started", "execution.completed",
    "execution.failed", "execution.cancelled",
)


class ProductionObservabilitySubscriber:

    def __init__(self, trace_collector, metrics_collector, cost_collector=None):
        self.trace_collector = trace_collector
        self.metrics_collector = metrics_collector
        self.cost_collector = cost_collector
        self._started = {}  # execution_id -> (trace_id, created_at datetime)

    def handle(self, event):
        event_type = getattr(event, "event_type", None)
        if event_type not in _EXECUTION_HANDLERS:
            return None
        handler = {
            "execution.created": self._on_created,
            "execution.started": self._on_started,
            "execution.completed": self._on_completed,
            "execution.failed": self._on_failed,
            "execution.cancelled": self._on_cancelled,
        }[event_type]
        handler(event)
        return None

    def _on_created(self, event):
        self.trace_collector.start_trace(
            trace_id=event.trace_id,
            tenant_id=event.tenant_id or "",
            agent_id=event.agent_id,
            agent_version=event.agent_version,
            execution_id=event.execution_id,
        )
        self._started[event.execution_id] = (event.trace_id, event.timestamp)

    def _on_started(self, event):
        span = ExecutionSpan(
            span_id=f"exec:{event.execution_id}",
            trace_id=event.trace_id,
            component=COMPONENT_AGENT,
            operation="execution",
            execution_id=event.execution_id,
        )
        try:
            self.trace_collector.add_span(span)
        except ValueError:
            pass  # trace not started (defensive; execution.created precedes)

    def _on_completed(self, event):
        self._finish(event, success=True)

    def _on_failed(self, event):
        self._finish(event, success=False)

    def _on_cancelled(self, event):
        self._finish(event, success=False)

    def _finish(self, event, success):
        latency_ms = self._latency_ms(event)
        self.trace_collector.finish_trace(
            event.trace_id, status=(TRACE_SUCCESS if success else TRACE_FAILED),
        )
        self.metrics_collector.record(AgentMetricSample(
            tenant_id=event.tenant_id or "",
            agent_id=event.agent_id,
            success=success,
            latency_ms=latency_ms,
            execution_id=event.execution_id,
        ))

    def _latency_ms(self, event):
        started = self._started.get(event.execution_id)
        if started is None:
            return 0.0
        return (event.timestamp - started[1]).total_seconds() * 1000.0


__all__ = ["ProductionObservabilitySubscriber"]
