from app.runtime.loop import AgentExecutionLoop


class AgentExecutor:
    """Backward-compatible adapter to the standard AgentExecutionLoop."""

    def __init__(
        self,
        agent,
        tool_runner,
        max_steps=10,
        agent_record=None,
        memory_guard=None,
    ):
        self.agent = agent
        self.tool_runner = tool_runner
        self.max_steps = max_steps
        self.agent_record = agent_record
        self.memory_guard = memory_guard

    def run(self, state):
        record = self.agent_record
        if record is None:
            record = type(
                "AgentRecord",
                (),
                {
                    "instance": self.agent,
                    "agent_id": getattr(self.agent, "agent_id", state.agent_name),
                    "version": getattr(self.agent, "version", None),
                    "definition": getattr(self.agent, "definition", None),
                },
            )()
        return AgentExecutionLoop(
            agent_record=record,
            tool_runner=self.tool_runner,
            memory_guard=self.memory_guard,
            max_steps=self.max_steps,
        ).run(state)
