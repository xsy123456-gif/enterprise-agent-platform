from app.runtime.executor import AgentExecutor


class RuntimeEngine:


    def __init__(
        self,
        agent_registry,
        tool_runner,
        max_steps=10
    ):

        self.agent_registry = agent_registry

        self.tool_runner = tool_runner

        self.max_steps = max_steps



    def run(
        self,
        state,
        agent_id=None,
        version=None
    ):

        selected_agent_id = agent_id or state.agent_name

        agent = self.agent_registry.get_agent(
            selected_agent_id,
            version
        )

        executor = AgentExecutor(
            agent=agent,
            tool_runner=self.tool_runner,
            max_steps=self.max_steps
        )

        return executor.run(
            state
        )
