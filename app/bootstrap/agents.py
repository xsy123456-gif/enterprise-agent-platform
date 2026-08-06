from app.agents.sales import SalesAgent
from app.registry.models import (
    Agent,
    AgentStatus,
    Capability,
    Policy,
    ToolBinding,
)


def register_builtin_agents(registry, llm):
    registry.register_capability(
        Capability(
            capability_id="customer_analysis",
            description="分析客户业务信息与历史记录",
        )
    )
    registry.register_capability(
        Capability(
            capability_id="visit_prepare",
            description="准备客户拜访材料",
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
        llm=llm,
        agent_id="sales_agent",
        version="0.1",
    )
    registry.register(
        Agent(
            agent_id="sales_agent",
            name="销售运营助手",
            version="0.1",
            description="分析客户信息并准备客户拜访材料",
            owner="sales_operations",
            status=AgentStatus.ACTIVE,
            capabilities=["customer_analysis", "visit_prepare"],
            policy_id=policy.policy_id,
            instance=sales_agent,
        )
    )
