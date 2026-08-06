from app.agents.base import BaseAgent
from app.agents.definition import AgentDefinition
from app.llm.prompts import SYSTEM_PROMPT


class SalesAgent(BaseAgent):
    """Sales domain definition; execution is owned by AgentExecutionLoop."""

    def __init__(self, llm, agent_id="sales_agent", version=None):
        super().__init__(
            llm=llm,
            agent_id=agent_id,
            version=version,
        )
        self.definition = AgentDefinition(
            agent_id=agent_id,
            version=version,
            system_prompt=SYSTEM_PROMPT,
            capabilities=["customer_analysis", "visit_prepare"],
            allowed_tools=["crm_query"],
            memory_policy="customer_memory",
        )
