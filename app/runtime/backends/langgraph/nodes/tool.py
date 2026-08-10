import uuid

from app.runtime.action import AgentAction


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
        action_data = dict(state.get("_action") or {})
        if action_data.get("type") != "tool" or not action_data.get("tool"):
            raise ValueError("ToolNode requires a pending tool call")
        action = AgentAction.tool_action(
            action_data["tool"], action_data.get("input")
        )
        execution_state = _ToolExecutionState(state)
        if self.validator is not None:
            self.validator.validate(action, execution_state)
        result = self.tool_runner.run(action, execution_state)
        return {
            "messages": execution_state.messages,
            "tool_results": execution_state.tool_results,
            "observation": result,
            "status": "observing",
        }
