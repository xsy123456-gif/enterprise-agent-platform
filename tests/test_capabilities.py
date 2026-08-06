import unittest

from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.registry.models import Agent, AgentStatus, ToolBinding
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository


class StubAgent:
    def think(self, state):
        return None


class CapabilityCatalogTest(unittest.TestCase):
    def setUp(self):
        self.catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        self.catalog.register(
            CapabilityDefinition(
                capability_id="customer_analysis",
                name="客户分析",
                description="获取并分析客户基本信息、业务信息和历史记录",
                examples=["查询客户资料", "分析客户背景"],
                risk_level="medium",
                required_permissions=["crm.customer.read"],
                allowed_tools=["crm_query"],
            )
        )

    def test_catalog_context_exposes_business_capability_not_tool_details(self):
        context = self.catalog.get_catalog_context()
        self.assertEqual("customer_analysis", context[0]["capability_id"])
        self.assertIn("查询客户资料", context[0]["examples"])
        self.assertNotIn("allowed_tools", context[0])

    def test_agent_registry_requires_catalog_capabilities(self):
        registry = AgentRegistry(
            InMemoryAgentRepository(),
            capability_catalog=self.catalog,
        )
        agent = Agent(
            agent_id="sales_agent",
            name="Sales",
            version="0.1",
            description="Sales",
            owner="sales",
            status=AgentStatus.ACTIVE,
            capabilities=["finance_salary_query"],
            instance=StubAgent(),
        )

        with self.assertRaisesRegex(ValueError, "unknown capability"):
            registry.register(agent)

    def test_tool_binding_is_checked_against_catalog(self):
        registry = AgentRegistry(
            InMemoryAgentRepository(),
            capability_catalog=self.catalog,
        )

        binding = ToolBinding(
            capability_id="customer_analysis",
            tool_name="crm_query",
            required_permission="crm.customer.read",
            risk_level="medium",
        )
        registry.bind_tool(binding)
        self.assertEqual([binding], registry.get_tool_bindings())

        with self.assertRaisesRegex(ValueError, "not allowed"):
            registry.bind_tool(
                ToolBinding(
                    capability_id="customer_analysis",
                    tool_name="payroll_query",
                    required_permission="crm.customer.read",
                    risk_level="medium",
                )
            )


if __name__ == "__main__":
    unittest.main()
