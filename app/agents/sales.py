from app.agents.base import BaseAgent


class SalesAgent(BaseAgent):
    """Legacy runtime identity; sales behavior now comes from its Manifest."""

    def __init__(self, llm, agent_id="sales_agent", version=None):
        super().__init__(
            llm=llm,
            agent_id=agent_id,
            version=version,
        )
