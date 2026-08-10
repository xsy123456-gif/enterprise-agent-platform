class CompilerValidationError(ValueError):
    pass


class CompilerValidator:
    """Validates control-plane references before a portable IR is created."""

    def validate(self, compile_input):
        definition = compile_input.agent_definition
        if not definition.agent_id or not definition.version:
            raise CompilerValidationError("Agent definition identity is required")
        if not definition.system_prompt:
            raise CompilerValidationError("Agent definition system_prompt is required")

        capabilities = []
        for capability_id in definition.capabilities:
            try:
                capability = compile_input.capability_catalog.get(capability_id)
            except KeyError as error:
                raise CompilerValidationError(
                    f"Unknown capability: {capability_id}"
                ) from error
            capabilities.append(capability)

        allowed_by_capability = set()
        for capability in capabilities:
            allowed_by_capability.update(getattr(capability, "allowed_tools", []) or [])
        for tool_name in definition.allowed_tools:
            if compile_input.tool_registry.get(tool_name) is None:
                raise CompilerValidationError(f"Unknown tool: {tool_name}")
            if tool_name not in allowed_by_capability:
                raise CompilerValidationError(
                    f"Tool is not bound to an Agent capability: {tool_name}"
                )

        if definition.policy_ref:
            try:
                compile_input.policy_registry.get_policy(definition.policy_ref)
            except KeyError as error:
                raise CompilerValidationError(
                    f"Unknown policy: {definition.policy_ref}"
                ) from error
        return compile_input
