class ReasoningNode:
    """Invoke an injected reasoning boundary; it performs no governance work."""

    def __init__(self, reasoner=None):
        self.reasoner = reasoner

    def __call__(self, state):
        messages = list(state.get("messages") or [])
        if self.reasoner is None:
            output = state.get("response") or state.get("input") or ""
        elif hasattr(self.reasoner, "reason"):
            output = self.reasoner.reason(messages)
        elif hasattr(self.reasoner, "chat"):
            output = self.reasoner.chat(messages)
        else:
            output = self.reasoner(messages)
        intermediate = dict(state.get("intermediate_results") or {})
        intermediate["reasoning_output"] = output
        return {
            "reasoning_output": output,
            "intermediate_results": intermediate,
            "status": "running",
        }
