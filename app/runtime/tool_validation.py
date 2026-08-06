class ToolValidationError(ValueError):
    pass


class ToolRequestValidator:
    """Validates an LLM tool request before it reaches ToolRunner."""

    def __init__(self, tool_runner, agent_registry=None):
        self.tool_runner = tool_runner
        self.agent_registry = agent_registry

    def validate(self, action, state):
        tool_name = action.tool
        tool = self.tool_runner.registry.get(tool_name)
        if tool is None:
            raise ToolValidationError(f"Tool not found: {tool_name}")

        definition = getattr(state, "agent_definition", None)
        allowed_tools = getattr(definition, "allowed_tools", [])
        if allowed_tools and tool_name not in allowed_tools:
            raise ToolValidationError(
                f"Tool is not allowed for Agent: {tool_name}"
            )

        if self.agent_registry is not None and state.capability:
            bindings = self.agent_registry.get_tool_bindings(state.capability)
            if bindings and not any(
                binding.tool_name == tool_name for binding in bindings
            ):
                raise ToolValidationError(
                    f"Tool is not bound to capability: {tool_name}"
                )

        if hasattr(tool, "validate_input") and not tool.validate_input(action.input):
            raise ToolValidationError(f"Invalid input for tool: {tool_name}")
        if action.input is None or action.input == "":
            raise ToolValidationError(f"Tool input is required: {tool_name}")
        return tool
