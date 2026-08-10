import uuid

from app.runtime.action import AgentAction
from app.tools.models import ToolCallRequest


class _ToolExecutionState:
    """Minimal platform-facing state consumed by ToolRunner."""

    def __init__(self, graph_state):
        metadata = dict(graph_state.get("metadata") or {})
        self.user_id = metadata.get("user_id")
        self.role = metadata.get("role")
        self.agent_name = graph_state.get("agent_id")
        self.capability = metadata.get("capability")
        self.agent_definition = metadata.get("agent_definition")
        self.messages = list(graph_state.get("messages") or [])
        self.tool_results = list(graph_state.get("tool_results") or [])
        self.last_tool_call_id = None

    def add_tool_call(self, tool_name, tool_input):
        call_id = f"call_{uuid.uuid4()}"
        self.last_tool_call_id = call_id
        self.messages.append({
            "role": "assistant",
            "tool_calls": [{
                "id": call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": str(tool_input)},
            }],
        })
        return call_id

    def add_tool_result(self, tool_call_id, result):
        self.tool_results.append(result)
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": str(result),
        })


class ToolNode:
    """Delegate governed execution to ToolRunner; never access a Tool directly."""

    def __init__(self, tool_runner=None, validator=None):
        self.tool_runner = tool_runner
        self.validator = validator

    def __call__(self, state):
        if self.tool_runner is None:
            raise RuntimeError("ToolNode requires an injected ToolRunner")
        pending = dict(state.get("pending_tool_call") or {})
        action_data = dict(state.get("_action") or {})
        tool_name = pending.get("tool") or action_data.get("tool")
        arguments = pending.get("arguments", action_data.get("input"))
        if not tool_name:
            raise ValueError("ToolNode requires a pending tool call")
        request = ToolCallRequest(
            tool_name=tool_name,
            arguments=arguments,
            trace_id=state.get("trace_id", "graph-trace"),
            execution_id=state.get("execution_id", "graph-execution"),
            agent_id=state.get("agent_id", "graph-agent"),
            user_id=(state.get("metadata") or {}).get("user_id", "graph-user"),
            agent_version=state.get("agent_version"),
            tenant_id=state.get("metadata", {}).get("tenant_id"),
            role=state.get("metadata", {}).get("role"),
            department_id=state.get("metadata", {}).get("department_id"),
            capability=state.get("metadata", {}).get("capability"),
            allowed_tools=tuple(state.get("metadata", {}).get("allowed_tools", ())),
        )
        execution_state = _ToolExecutionState(state)
        result = self.tool_runner.execute(request)
        if not result.success:
            raise RuntimeError(result.error or "Tool execution failed")
        call_id = execution_state.add_tool_call(request.tool_name, request.arguments)
        execution_state.add_tool_result(call_id, result.output)
        return {
            "messages": execution_state.messages,
            "tool_results": [
                *list(state.get("tool_results") or []), result.to_dict()
            ],
            "observation": result.to_dict(),
            "status": "observing",
        }
