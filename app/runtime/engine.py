from app.runtime.loop import AgentExecutionLoop


class RuntimeEngine:


    def __init__(
        self,
        agent_registry,
        tool_runner,
        max_steps=10,
        memory_guard=None,
    ):

        self.agent_registry = agent_registry

        self.tool_runner = tool_runner

        self.max_steps = max_steps

        self.memory_guard = memory_guard



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
            memory_guard=self.memory_guard,
            agent_registry=self.agent_registry,
            max_steps=self.max_steps,
        )
        return loop.run(state)
