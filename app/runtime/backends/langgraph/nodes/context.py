class ContextNode:
    """Normalize graph execution context without invoking platform services."""

    def __call__(self, state):
        messages = list(state.get("messages") or [])
        input_text = state.get("input") or ""
        if input_text and not messages:
            messages.append({"role": "user", "content": input_text})
        return {
            "messages": messages,
            "intermediate_results": dict(
                state.get("intermediate_results") or {}
            ),
            "tool_results": list(state.get("tool_results") or []),
            "metadata": dict(state.get("metadata") or {}),
            "status": "running",
        }
