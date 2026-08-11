import json

from app.runtime.action import AgentAction
from app.runtime.backends.langgraph.nodes.tool import ToolNode


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
            item.get("role") == "system"
            and system_prompt in str(item.get("content") or "")
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


class MemoryNodeAdapter:
    def __init__(self, memory_adapter, agent_registry, node_definition):
        if memory_adapter is None or agent_registry is None:
            raise ValueError("MemoryNodeAdapter requires Memory Port and Agent Registry")
        self.memory_adapter = memory_adapter
        self.agent_registry = agent_registry
        self.node_definition = node_definition

    def __call__(self, state):
        # Memory read context is prepared at the Runtime boundary before graph
        # execution. The IR node remains a dependency marker only.
        return {"status": "running"}


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
            return ToolNode(tool_runner=self.tool_runner)
        if name == "MemoryNodeAdapter":
            return MemoryNodeAdapter(
                self.memory_adapter, self.agent_registry, node_definition
            )
        if name == "GovernanceNodeAdapter":
            return GovernanceNodeAdapter(self.agent_registry, node_definition)
        raise ValueError(f"No runtime Node adapter registered: {name}")
