class ResponseNode:
    """Materialize the final graph response without writing Memory."""

    def __call__(self, state):
        governance = dict(state.get("governance_decision") or {})
        if governance.get("status") == "deny":
            reason = governance.get("reason", "execution denied")
            return {"response": reason, "status": "failed"}
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
