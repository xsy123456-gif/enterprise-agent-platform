from app.runtime.loop import AgentExecutionLoop
from app.runtime.context_builder import AgentContextBuilder


class AgentExecutor:
    """Backward-compatible adapter to the standard AgentExecutionLoop."""

    def __init__(
        self,
        agent,
        tool_runner,
        max_steps=10,
        agent_record=None,
        memory_adapter=None,
    ):
        self.agent = agent
        self.tool_runner = tool_runner
        self.max_steps = max_steps
        self.agent_record = agent_record
        self.memory_adapter = memory_adapter

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
            context_builder=AgentContextBuilder(self.memory_adapter),
            max_steps=self.max_steps,
        ).run(state)
