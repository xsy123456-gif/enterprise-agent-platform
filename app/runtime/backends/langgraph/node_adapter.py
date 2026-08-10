import json
import uuid

from app.runtime.action import AgentAction
from app.runtime.tool_validation import ToolRequestValidator


def _parse_agent_action(response):
    if isinstance(response, AgentAction):
        return response
    if isinstance(response, dict):
        data = response
    elif isinstance(response, str):
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return AgentAction.finish_action(response)
    else:
        raise ValueError("Agent response must be text, an object, or AgentAction")
    if data.get("type") == "tool" or data.get("action") == "tool_call":
        return AgentAction.tool_action(
            data.get("tool"), data.get("input", data.get("arguments"))
        )
    if data.get("type") == "finish" or data.get("action") == "finish":
        return AgentAction.finish_action(data.get("output"))
    raise ValueError("Invalid Agent action")


class AgentNodeAdapter:
    def __init__(self, agent_registry, node_definition):
        if agent_registry is None:
            raise ValueError("AgentNodeAdapter requires Agent Registry")
        self.agent_registry = agent_registry
        self.node_definition = node_definition

    def __call__(self, state):
        record = self.agent_registry.get(state["agent_id"], state["agent_version"])
        definition = record.definition or getattr(record.instance, "definition", None)
        messages = list(state.get("messages") or [])
        system_prompt = getattr(definition, "system_prompt", None)
        if system_prompt and not any(
            item.get("role") == "system" and item.get("content") == system_prompt
            for item in messages if isinstance(item, dict)
        ):
            messages.insert(0, {"role": "system", "content": system_prompt})
        action = _parse_agent_action(record.instance.reason(messages))
        if action.type == AgentAction.FINISH:
            messages.append({"role": "assistant", "content": action.output})
            return {
                "messages": messages,
                "response": action.output,
                "status": "completed",
                "_action": {"type": "finish", "output": action.output},
            }
        return {
            "messages": messages,
            "status": "running",
            "_action": {
                "type": "tool",
                "tool": action.tool,
                "input": action.input,
            },
        }


class _GovernedToolState:
    def __init__(self, graph_state, definition):
        metadata = graph_state.get("metadata") or {}
        self.user_id = metadata.get("user_id")
        self.role = metadata.get("role")
        if not self.user_id or not self.role:
            raise ValueError("Tool execution requires metadata.user_id and metadata.role")
        self.agent_name = graph_state["agent_id"]
        self.capability = metadata.get("capability")
        self.agent_definition = definition
        self.messages = list(graph_state.get("messages") or [])
        self.tool_results = list(graph_state.get("tool_results") or [])
        self.last_tool_call_id = None

    def add_tool_call(self, tool_name, input):
        tool_call_id = f"call_{uuid.uuid4()}"
        self.last_tool_call_id = tool_call_id
        self.messages.append({
            "role": "assistant",
            "tool_calls": [{
                "id": tool_call_id,
                "type": "function",
                "function": {"name": tool_name, "arguments": str(input)},
            }],
        })
        return tool_call_id

    def add_tool_result(self, tool_call_id, result):
        self.tool_results.append(result)
        self.messages.append({
            "role": "tool", "tool_call_id": tool_call_id, "content": str(result),
        })


class ToolNodeAdapter:
    """Mandatory governance path; never delegates to LangGraph ToolNode."""

    def __init__(self, tool_runner, agent_registry, node_definition):
        if tool_runner is None or agent_registry is None:
            raise ValueError("ToolNodeAdapter requires ToolRunner and Agent Registry")
        self.tool_runner = tool_runner
        self.agent_registry = agent_registry
        self.validator = ToolRequestValidator(tool_runner, agent_registry)
        self.node_definition = node_definition

    def __call__(self, state):
        action_data = state.get("_action") or {}
        tool_name = action_data.get("tool")
        bound_tool = (self.node_definition.get("bindings") or {}).get("tool_name")
        if tool_name != bound_tool:
            raise ValueError(
                f"Tool route does not match node binding: {tool_name} != {bound_tool}"
            )
        action = AgentAction.tool_action(tool_name, action_data.get("input"))
        record = self.agent_registry.get(state["agent_id"], state["agent_version"])
        definition = record.definition or getattr(record.instance, "definition", None)
        governed_state = _GovernedToolState(state, definition)
        self.validator.validate(action, governed_state)
        self.tool_runner.run(action, governed_state)
        return {
            "messages": governed_state.messages,
            "tool_results": governed_state.tool_results,
            "status": "running",
            "_action": None,
        }


class _MemoryState:
    def __init__(self, graph_state):
        metadata = graph_state.get("metadata") or {}
        self.tenant_id = graph_state["tenant_id"]
        self.user_id = metadata.get("user_id")
        if not self.user_id:
            raise ValueError("Memory execution requires metadata.user_id")
        self.subject_id = metadata.get("subject_id") or self.user_id
        self.agent_name = graph_state["agent_id"]
        self.department_id = metadata.get("department_id")
        self.task = metadata.get("task") or ""
        self.trace_id = graph_state["trace_id"]


class MemoryNodeAdapter:
    def __init__(self, memory_adapter, agent_registry, node_definition):
        if memory_adapter is None or agent_registry is None:
            raise ValueError("MemoryNodeAdapter requires Memory Port and Agent Registry")
        self.memory_adapter = memory_adapter
        self.agent_registry = agent_registry
        self.node_definition = node_definition

    def __call__(self, state):
        record = self.agent_registry.get(state["agent_id"], state["agent_version"])
        definition = record.definition or getattr(record.instance, "definition", None)
        context = self.memory_adapter.retrieve(_MemoryState(state), definition)
        return {"memory_context": context, "status": "running"}


class GovernanceNodeAdapter:
    def __init__(self, agent_registry, node_definition):
        if agent_registry is None:
            raise ValueError("GovernanceNodeAdapter requires Agent Registry")
        self.agent_registry = agent_registry
        self.node_definition = node_definition

    def __call__(self, state):
        policy_ref = (self.node_definition.get("governance") or {}).get("policy_ref")
        if policy_ref:
            self.agent_registry.get_policy(policy_ref)
        return {"status": "running"}


class LangGraphNodeAdapterRegistry:
    """Composition boundary between backend nodes and platform service ports."""

    def __init__(self, agent_registry=None, tool_runner=None, memory_adapter=None,
                 custom_adapters=None):
        self.agent_registry = agent_registry
        self.tool_runner = tool_runner
        self.memory_adapter = memory_adapter
        self.custom_adapters = dict(custom_adapters or {})

    def build(self, node_definition):
        name = node_definition["adapter"]
        if name in self.custom_adapters:
            return self.custom_adapters[name](node_definition)
        if name == "AgentNodeAdapter":
            return AgentNodeAdapter(self.agent_registry, node_definition)
        if name == "ToolNodeAdapter":
            return ToolNodeAdapter(
                self.tool_runner, self.agent_registry, node_definition
            )
        if name == "MemoryNodeAdapter":
            return MemoryNodeAdapter(
                self.memory_adapter, self.agent_registry, node_definition
            )
        if name == "GovernanceNodeAdapter":
            return GovernanceNodeAdapter(self.agent_registry, node_definition)
        raise ValueError(f"No runtime Node adapter registered: {name}")
