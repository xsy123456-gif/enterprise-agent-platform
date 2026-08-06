from app.agents.base import BaseAgent


class ManifestAgent(BaseAgent):
    """A generic runtime Agent configured entirely by AgentDefinition."""

    def __init__(self, llm, definition):
        super().__init__(
            llm=llm,
            agent_id=definition.agent_id,
            version=definition.version,
        )
        self.definition = definition
