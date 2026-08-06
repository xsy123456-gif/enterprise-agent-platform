from app.agents.sales import SalesAgent
from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.registry.models import Agent, AgentStatus, Policy, ToolBinding
from app.sources.base import AgentSource


class BuiltinAgentSource(AgentSource):
    """Provides the Agents bundled with this application."""

    def __init__(self, llm, catalog=None):
        self.llm = llm
        self.catalog = catalog or CapabilityCatalog(InMemoryCapabilityRepository())

    def load(self, registry):
        self.catalog.register(
            CapabilityDefinition(
                capability_id="customer_analysis",
                name="客户分析",
                description="分析客户业务信息与历史记录",
                examples=["查询客户资料", "分析客户背景"],
                risk_level="medium",
                required_permissions=["crm.customer.read"],
                allowed_tools=["crm_query"],
            )
        )
        self.catalog.register(
            CapabilityDefinition(
                capability_id="visit_prepare",
                name="拜访资料准备",
                description="准备客户拜访材料",
                examples=["准备客户拜访资料", "生成客户拜访方案"],
                risk_level="low",
            )
        )

        policy = Policy(
            policy_id="sales_agent_policy",
            permission_rules=["crm.customer.read"],
            data_scope=["sales_department"],
            audit_level="full",
        )
        registry.register_policy(policy)

        registry.bind_tool(
            ToolBinding(
                capability_id="customer_analysis",
                tool_name="crm_query",
                required_permission="crm.customer.read",
                risk_level="low",
            )
        )

        sales_agent = SalesAgent(
            llm=self.llm,
            agent_id="sales_agent",
            version="0.1",
        )
        definition = Agent(
            agent_id="sales_agent",
            name="销售运营助手",
            version="0.1",
            description="分析客户信息并准备客户拜访材料",
            owner="sales_operations",
            status=AgentStatus.ACTIVE,
            capabilities=["customer_analysis", "visit_prepare"],
            policy_id=policy.policy_id,
            instance=sales_agent,
            definition=sales_agent.definition,
        )
        registry.register(definition)
        return [definition]
