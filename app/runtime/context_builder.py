import json


class AgentContextBuilder:
    """Builds model-facing context without performing execution."""

    def build_messages(self, state, definition):
        messages = []
        system_prompt = getattr(definition, "system_prompt", None)
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        execution_context = {
            "task_id": getattr(state, "task_id", None),
            "step_id": getattr(state, "step_id", None),
            "capability": getattr(state, "capability", None),
            "goal": getattr(state, "goal", state.task),
            "agent_definition": getattr(definition, "to_dict", lambda: None)(),
            "memory_context": getattr(state, "memory_context", []),
            "available_tools": getattr(state, "available_tools", []),
        }
        messages.append(
            {
                "role": "system",
                "content": "Execution context:\n"
                + json.dumps(execution_context, ensure_ascii=False),
            }
        )
        messages.extend(state.messages)
        return messages
