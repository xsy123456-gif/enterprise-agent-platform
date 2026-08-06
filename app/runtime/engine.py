from app.runtime.loop import AgentExecutionLoop
from app.runtime.context_builder import AgentContextBuilder


class RuntimeEngine:


    def __init__(
        self,
        agent_registry,
        tool_runner,
        max_steps=10,
        memory_adapter=None,
    ):

        self.agent_registry = agent_registry

        self.tool_runner = tool_runner

        self.max_steps = max_steps

        self.memory_adapter = memory_adapter



    def run(
        self,
        state,
        agent_id=None,
        version=None
    ):

        selected_agent_id = agent_id or state.agent_name

        agent_record = self.agent_registry.get(
            selected_agent_id,
            version,
        )
        loop = AgentExecutionLoop(
            agent_record=agent_record,
            tool_runner=self.tool_runner,
            agent_registry=self.agent_registry,
            context_builder=AgentContextBuilder(self.memory_adapter),
            max_steps=self.max_steps,
        )
        return loop.run(state)
