class ObservationNode:
    """Record a Tool observation without making a business decision."""

    def __call__(self, state):
        intermediate = dict(state.get("intermediate_results") or {})
        observations = list(intermediate.get("observations") or [])
        if "observation" in state:
            observations.append(state.get("observation"))
        intermediate["observations"] = observations
        return {
            "intermediate_results": intermediate,
            "observation": None,
            "pending_tool_call": None,
            "_action": None,
            "tool_call_request": None,
            "status": "running",
        }
