"""Agent trace + span model (Phase 15.1).

Observability only: records what ran, how long, at what cost — never the
business reason (that is the Diagnostic Kernel), and never secret / credential /
raw sensitive data.
"""

from dataclasses import dataclass, field

from app.core.time import utc_now

TRACE_RUNNING = "RUNNING"
TRACE_SUCCESS = "SUCCESS"
TRACE_FAILED = "FAILED"
TRACE_CANCELLED = "CANCELLED"
TRACE_STATUSES = frozenset({TRACE_RUNNING, TRACE_SUCCESS, TRACE_FAILED,
                            TRACE_CANCELLED})

COMPONENT_AGENT = "agent"
COMPONENT_SKILL = "skill"
COMPONENT_PLAN = "plan"
COMPONENT_TOOL = "tool"
COMPONENT_LLM = "llm"
COMPONENTS = frozenset({
    COMPONENT_AGENT, COMPONENT_SKILL, COMPONENT_PLAN, COMPONENT_TOOL,
    COMPONENT_LLM,
})

FORBIDDEN_OBSERVABILITY_KEYS = (
    "secret", "credential", "token", "password", "raw_data", "private",
    "sensitive", "authorization", "api_key", "apikey", "refresh_token",
    "secret_reference", "bearer",
)


@dataclass(frozen=True)
class AgentTrace:
    trace_id: str
    parent_trace_id: str = ""
    tenant_id: str = ""
    agent_id: str = ""
    agent_version: str = ""
    task_id: str = ""
    execution_id: str = ""
    start_time: str = field(default_factory=utc_now)
    end_time: str = ""
    status: str = TRACE_RUNNING

    def __post_init__(self):
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.status not in TRACE_STATUSES:
            raise ValueError(f"unknown trace status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "parent_trace_id": self.parent_trace_id,
            "tenant_id": self.tenant_id,
            "agent_id": self.agent_id,
            "agent_version": self.agent_version,
            "task_id": self.task_id,
            "execution_id": self.execution_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
        }


@dataclass(frozen=True)
class ExecutionSpan:
    span_id: str
    trace_id: str
    component: str
    operation: str = ""
    duration: float = 0.0
    status: str = TRACE_SUCCESS
    metadata: dict = field(default_factory=dict)
    execution_id: str = ""

    def __post_init__(self):
        object.__setattr__(self, "metadata", dict(self.metadata or {}))
        if not self.span_id:
            raise ValueError("span_id is required")
        if not self.trace_id:
            raise ValueError("trace_id is required")
        if self.component not in COMPONENTS:
            raise ValueError(f"unknown component: {self.component}")
        for key in FORBIDDEN_OBSERVABILITY_KEYS:
            if key in self.metadata:
                raise ValueError(
                    f"span metadata must not carry forbidden key {key!r}"
                )

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "component": self.component,
            "operation": self.operation,
            "duration": self.duration,
            "status": self.status,
            "metadata": dict(self.metadata),
            "execution_id": self.execution_id,
        }


class TraceCollector:

    def __init__(self):
        self._traces = {}
        self._spans = {}

    def start_trace(self, trace_id, tenant_id="", agent_id="", agent_version="",
                    task_id="", parent_trace_id="", execution_id="") -> AgentTrace:
        trace = AgentTrace(
            trace_id=trace_id, parent_trace_id=parent_trace_id,
            tenant_id=tenant_id, agent_id=agent_id, agent_version=agent_version,
            task_id=task_id, execution_id=execution_id)
        self._traces[trace_id] = trace
        self._spans.setdefault(trace_id, [])
        return trace

    def finish_trace(self, trace_id, status=TRACE_SUCCESS, end_time=None):
        trace = self._traces[trace_id]
        finished = AgentTrace(
            trace_id=trace.trace_id, parent_trace_id=trace.parent_trace_id,
            tenant_id=trace.tenant_id, agent_id=trace.agent_id,
            agent_version=trace.agent_version, task_id=trace.task_id,
            execution_id=trace.execution_id,
            start_time=trace.start_time, end_time=end_time or utc_now(),
            status=status,
        )
        self._traces[trace_id] = finished
        return finished

    def add_span(self, span: ExecutionSpan) -> ExecutionSpan:
        if span.trace_id not in self._traces:
            raise ValueError(f"span references unknown trace {span.trace_id!r}")
        self._spans.setdefault(span.trace_id, []).append(span)
        return span

    def trace(self, trace_id):
        return self._traces.get(trace_id)

    def spans_for(self, trace_id):
        return tuple(self._spans.get(trace_id, ()))


__all__ = [
    "AgentTrace",
    "ExecutionSpan",
    "TraceCollector",
    "TRACE_STATUSES",
    "TRACE_RUNNING",
    "TRACE_SUCCESS",
    "TRACE_FAILED",
    "TRACE_CANCELLED",
    "COMPONENTS",
    "COMPONENT_AGENT",
    "COMPONENT_SKILL",
    "COMPONENT_PLAN",
    "COMPONENT_TOOL",
    "COMPONENT_LLM",
    "FORBIDDEN_OBSERVABILITY_KEYS",
]
