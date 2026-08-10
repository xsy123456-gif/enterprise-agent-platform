class ResponseNode:
    """Materialize the final graph response without writing Memory."""

    def __call__(self, state):
        action = dict(state.get("_action") or {})
        output = action.get("output")
        if output is None:
            output = state.get("reasoning_output")
        messages = list(state.get("messages") or [])
        if output is not None:
            messages.append({"role": "assistant", "content": output})
        return {
            "response": output,
            "messages": messages,
            "status": "completed",
        }
