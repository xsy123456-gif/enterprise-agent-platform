import json


class ToolDecisionNode:
    """Convert reasoning output to an execution intent without running a Tool."""

    def __call__(self, state):
        output = state.get("reasoning_output")
        decision = self._parse(output)
        if decision["type"] == "tool":
            return {
                "_action": decision,
                "tool_call_request": {
                    "tool": decision["tool"],
                    "arguments": decision.get("input"),
                },
                "status": "waiting_tool",
            }
        return {
            "_action": decision,
            "tool_call_request": None,
            "status": "responding",
        }

    @staticmethod
    def _parse(output):
        if isinstance(output, dict):
            data = dict(output)
        elif isinstance(output, str):
            text = output.strip()
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                return {"type": "finish", "output": output}
        else:
            return {"type": "finish", "output": output}
        if data.get("action") == "tool_call" or data.get("type") == "tool":
            return {
                "type": "tool",
                "tool": data.get("tool"),
                "input": data.get("arguments", data.get("input")),
            }
        if data.get("action") == "finish" or data.get("type") == "finish":
            return {"type": "finish", "output": data.get("output")}
        return {"type": "finish", "output": output}
