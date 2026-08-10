from app.events.models import Event
from app.tools.models import ToolCallRequest, ToolResult


class ToolRunner:
    """The platform's sole Tool execution boundary."""

    def __init__(self, registry, permission, audit, event_bus, agent_registry=None):
        self.registry = registry
        self.permission = permission
        self.audit = audit
        self.event_bus = event_bus
        self.agent_registry = agent_registry

    def execute(self, request: ToolCallRequest) -> ToolResult:
        if not isinstance(request, ToolCallRequest):
            raise TypeError("ToolRunner.execute requires ToolCallRequest")
        tool = self.registry.get(request.tool_name)
        if tool is None:
            result = ToolResult(
                request.tool_name, False,
                error=f"Tool not found: {request.tool_name}",
            )
            self._publish("tool.failed", request, {"error": result.error})
            return result

        if request.allowed_tools and request.tool_name not in request.allowed_tools:
            return self._deny(request, "Tool is not allowed for Agent")
        if self.agent_registry is not None:
            record = self.agent_registry.get(request.agent_id, request.agent_version)
            definition = record.definition or getattr(record.instance, "definition", None)
            allowed_tools = tuple(getattr(definition, "allowed_tools", []) or [])
            if allowed_tools and request.tool_name not in allowed_tools:
                return self._deny(request, "Tool is not allowed for Agent")
        if (
            self.agent_registry is not None and request.capability
        ):
            bindings = self.agent_registry.get_tool_bindings(request.capability)
            if bindings and not any(
                binding.tool_name == request.tool_name for binding in bindings
            ):
                return self._deny(request, "Tool is not bound to capability")

        if hasattr(tool, "validate_input") and not tool.validate_input(request.arguments):
            return self._deny(request, "Invalid input for tool")

        allowed = self.permission.check(request.role, request.tool_name)
        self.audit.record(
            user=request.user_id,
            agent=request.agent_id,
            tool=request.tool_name,
            action="allow" if allowed else "deny",
            detail=request.arguments,
        )
        if not allowed:
            return self._deny(request, "Permission denied", audit=False)

        self._publish("tool.called", request, {"input": request.arguments})
        try:
            output = tool.execute(request.arguments)
        except Exception as error:
            self._publish("tool.failed", request, {"error": str(error)})
            return ToolResult(request.tool_name, False, error=str(error))
        self._publish("tool.completed", request, {"result": output})
        return ToolResult(request.tool_name, True, output=output)

    def run(self, action, state):
        """Legacy CurrentRuntime wrapper; all actual execution goes through execute."""
        request = ToolCallRequest(
            tool_name=action.tool,
            arguments=action.input,
            trace_id=getattr(state, "trace_id", "runtime-trace"),
            execution_id=getattr(state, "task_id", None) or "runtime-execution",
            agent_id=state.agent_name,
            user_id=state.user_id,
            agent_version=getattr(state, "agent_version", None),
            tenant_id=getattr(state, "tenant_id", None),
            role=state.role,
            department_id=getattr(state, "department_id", None),
            capability=getattr(state, "capability", None),
            allowed_tools=tuple(
                getattr(getattr(state, "agent_definition", None), "allowed_tools", [])
                or []
            ),
            legacy_event_compat=True,
        )
        call_id = state.add_tool_call(action.tool, action.input)
        result = self.execute(request)
        if not result.success:
            raise RuntimeError(result.error or "Tool execution failed")
        state.add_tool_result(call_id, result.output)
        return result.output

    def _deny(self, request, reason, audit=True):
        if audit:
            self.audit.record(
                user=request.user_id, agent=request.agent_id,
                tool=request.tool_name, action="deny", detail=request.arguments,
            )
        self._publish("tool.denied", request, {"error": reason})
        return ToolResult(request.tool_name, False, error=reason)

    def _publish(self, event_type, request, payload):
        event_payload = {
            "request_id": request.request_id,
            "trace_id": request.trace_id,
            "execution_id": request.execution_id,
            "user": request.user_id,
            "agent": request.agent_id,
            "tool": request.tool_name,
            **payload,
        }
        if request.legacy_event_compat:
            if event_type == "tool.completed":
                self.event_bus.publish(Event("tool_completed", event_payload))
            return
        self.event_bus.publish(Event(event_type, {
            **event_payload,
        }))
