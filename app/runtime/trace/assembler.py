from dataclasses import replace
from datetime import datetime
import uuid

from app.runtime.governance.events import RuntimeEvent
from app.runtime.governance.trace import BackendSpan, ExecutionTrace, NodeSpan
from app.storage.exceptions import NotFoundError


class TraceAssembler:
    """Materialize backend-neutral traces from canonical RuntimeEvent facts."""

    SAFE_ATTRIBUTES = {
        "node_id", "node_type", "tool", "tool_name", "request_id",
        "approval_id", "memory_event_id", "accepted", "result_count",
        "model", "provider", "capability", "retry_count", "checkpoint_id",
        "sender_agent_id", "receiver_agent_id", "message_type", "payload_size",
    }

    STARTS = {
        "graph.started": ("GRAPH", "graph"),
        "node.started": ("NODE", None),
        "tool.called": ("TOOL", None),
        "approval.requested": ("GOVERNANCE", "approval"),
        "memory.write.requested": ("MEMORY", "memory.write"),
    }
    ENDS = {
        "graph.completed": ("GRAPH", "graph", "OK"),
        "graph.failed": ("GRAPH", "graph", "ERROR"),
        "node.completed": ("NODE", None, "OK"),
        "node.failed": ("NODE", None, "ERROR"),
        "tool.completed": ("TOOL", None, "OK"),
        "tool.denied": ("TOOL", None, "DENIED"),
        "tool.failed": ("TOOL", None, "ERROR"),
        "approval.completed": ("GOVERNANCE", "approval", "OK"),
        "memory.write.completed": ("MEMORY", "memory.write", "OK"),
        "memory.write.failed": ("MEMORY", "memory.write", "ERROR"),
    }

    def __init__(self, repository):
        self.repository = repository

    def consume(self, event):
        if not isinstance(event, RuntimeEvent):
            raise TypeError("TraceAssembler requires canonical RuntimeEvent")
        trace = self._ensure_trace(event)
        safe_event = replace(event, payload=self._safe_attributes(event.payload))
        self.repository.append_event(safe_event)
        if event.event_type in self.STARTS:
            category, fixed_name = self.STARTS[event.event_type]
            self._open_span(event, trace, category, fixed_name)
        elif event.event_type in self.ENDS:
            category, fixed_name, status = self.ENDS[event.event_type]
            self._close_span(event, trace, category, fixed_name, status)
        elif event.event_type == "guard.checked":
            self._instant_span(event, trace, "GOVERNANCE", "guard.checked")
        elif event.event_type.startswith("agent.message."):
            self._instant_span(event, trace, "MESSAGE", event.event_type)
        if event.event_type in {
            "execution.completed", "execution.failed", "execution.cancelled",
            "graph.completed", "graph.failed",
        }:
            self._close_trace(event, trace)
        return self.repository.get(trace.trace_id)

    def _ensure_trace(self, event):
        try:
            return self.repository.get(event.trace_id)
        except NotFoundError:
            root_id = event.span_id or str(uuid.uuid4())
            trace = ExecutionTrace(
                trace_id=event.trace_id, execution_id=event.execution_id,
                agent_id=event.agent_id, artifact_id=event.artifact_id,
                backend_type=event.backend_type, status="RUNNING",
                root_span_id=root_id, start_time=event.timestamp,
                agent_version=event.agent_version,
                artifact_hash=event.artifact_hash,
                parent_agent_id=event.parent_agent_id,
                agent_execution_id=event.agent_execution_id,
                invocation_id=event.invocation_id,
                message_id=event.message_id,
                parent_agent_execution_id=event.parent_agent_execution_id,
                child_agent_execution_id=event.child_agent_execution_id,
                graph_node_id=event.graph_node_id,
                parallel_group_id=event.parallel_group_id,
            )
            self.repository.append(trace)
            self.repository.append_span(NodeSpan(
                trace_id=trace.trace_id, execution_id=trace.execution_id,
                node_id="execution", node_type="EXECUTION", span_type="EXECUTION",
                name="execution", status="RUNNING", input_summary="",
                output_summary="", span_id=root_id, start_time=event.timestamp,
                agent_id=event.agent_id, agent_version=event.agent_version,
                artifact_hash=event.artifact_hash, backend_type=event.backend_type,
                parent_agent_id=event.parent_agent_id,
                agent_execution_id=event.agent_execution_id,
                invocation_id=event.invocation_id,
                message_id=event.message_id,
                parent_agent_execution_id=event.parent_agent_execution_id,
                child_agent_execution_id=event.child_agent_execution_id,
                graph_node_id=event.graph_node_id,
                parallel_group_id=event.parallel_group_id,
            ))
            return trace

    def _open_span(self, event, trace, category, fixed_name):
        name = fixed_name or self._operation_name(event, category)
        parent = event.parent_span_id or self._parent_span(trace.trace_id, category)
        span = NodeSpan(
            trace_id=trace.trace_id, execution_id=trace.execution_id,
            node_id=name, node_type=category, span_type=category, name=name,
            status="RUNNING", input_summary="", output_summary="",
            span_id=event.span_id or str(uuid.uuid4()), parent_span_id=parent,
            operation_id=self._operation_id(event), start_time=event.timestamp,
            agent_id=event.agent_id, agent_version=event.agent_version,
            artifact_hash=event.artifact_hash, backend_type=event.backend_type,
            attributes=self._safe_attributes(event.payload),
            parent_agent_id=event.parent_agent_id,
            agent_execution_id=event.agent_execution_id,
            invocation_id=event.invocation_id,
            message_id=event.message_id,
            parent_agent_execution_id=event.parent_agent_execution_id,
            child_agent_execution_id=event.child_agent_execution_id,
            graph_node_id=event.graph_node_id,
            parallel_group_id=event.parallel_group_id,
        )
        self.repository.append_span(span)
        if category == "NODE":
            self._reparent_pending_operations(span, trace.root_span_id)
        if event.backend_metadata:
            self.repository.append_span(BackendSpan(
                backend_type=event.backend_type,
                backend_metadata=dict(event.backend_metadata),
                trace_id=trace.trace_id, execution_id=trace.execution_id,
                parent_span_id=span.span_id,
                operation_id=span.operation_id, status="OK",
                start_time=event.timestamp, end_time=event.timestamp,
            ))

    def _close_span(self, event, trace, category, fixed_name, status):
        name = fixed_name or self._operation_name(event, category)
        candidates = [
            span for span in self.repository.list_spans(trace.trace_id)
            if isinstance(span, NodeSpan) and span.span_type == category
            and span.status == "RUNNING"
            and (span.operation_id == self._operation_id(event) if event.operation_id or event.payload.get("request_id") else span.name == name)
        ]
        if not candidates:
            self._open_span(event, trace, category, fixed_name)
            candidates = [
                span for span in self.repository.list_spans(trace.trace_id)
                if isinstance(span, NodeSpan) and span.span_type == category
                and span.status == "RUNNING" and span.name == name
            ]
        span = candidates[-1]
        self.repository.update_span(replace(
            span, status=status, end_time=event.timestamp,
            error=self._safe_error(event.payload.get("error")) if status == "ERROR" else None,
            attributes={**span.attributes, **self._safe_attributes(event.payload)},
        ))

    def _instant_span(self, event, trace, category, name):
        self._open_span(event, trace, category, name)
        spans = self.repository.list_spans(trace.trace_id)
        span = next(span for span in reversed(spans) if isinstance(span, NodeSpan) and span.name == name)
        action = event.payload.get("action") or event.payload.get("status")
        status = "DENIED" if action == "deny" else "OK"
        self.repository.update_span(replace(span, status=status, end_time=event.timestamp))

    def _close_trace(self, event, trace):
        status = (
            "OK" if event.event_type in {"execution.completed", "graph.completed"}
            else "ERROR"
        )
        self.repository.update_trace(replace(
            trace, status=status, end_time=event.timestamp
        ))
        root = next(
            span for span in self.repository.list_spans(trace.trace_id)
            if getattr(span, "span_id", None) == trace.root_span_id
        )
        self.repository.update_span(replace(root, status=status, end_time=event.timestamp))

    def _parent_span(self, trace_id, category):
        spans = self.repository.list_spans(trace_id)
        if category in {"TOOL", "GOVERNANCE"}:
            running_nodes = [
                span for span in spans if isinstance(span, NodeSpan)
                and span.span_type == "NODE" and span.status == "RUNNING"
            ]
            if running_nodes:
                return running_nodes[-1].span_id
        graph = [
            span for span in spans if isinstance(span, NodeSpan)
            and span.span_type == "GRAPH" and span.status == "RUNNING"
        ]
        if graph:
            return graph[-1].span_id
        return self.repository.get(trace_id).root_span_id

    def _reparent_pending_operations(self, node_span, root_span_id):
        for span in self.repository.list_spans(node_span.trace_id):
            if (
                isinstance(span, NodeSpan)
                and span.span_type in {"TOOL", "GOVERNANCE"}
                and span.parent_span_id == root_span_id
                and span.start_time >= node_span.start_time
            ):
                self.repository.update_span(replace(
                    span, parent_span_id=node_span.span_id
                ))

    @staticmethod
    def _operation_id(event):
        return event.operation_id or event.payload.get("request_id") or event.event_id

    @staticmethod
    def _operation_name(event, category):
        if category == "NODE":
            return event.node_id or event.payload.get("node_id") or "node"
        if category == "TOOL":
            return event.payload.get("tool_name") or event.payload.get("tool") or "tool"
        return category.lower()

    @classmethod
    def _safe_attributes(cls, payload):
        return {
            key: value for key, value in dict(payload or {}).items()
            if key in cls.SAFE_ATTRIBUTES and isinstance(value, (str, int, float, bool, type(None)))
        }

    @staticmethod
    def _safe_error(error):
        if error is None:
            return None
        text = str(error)[:256]
        for marker in ("password", "api_key", "token", "secret"):
            if marker in text.lower():
                return "redacted observability error"
        return text
