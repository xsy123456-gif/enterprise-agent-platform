from pathlib import Path

from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.manifest.loader import ManifestLoader
from app.manifest.parser import ManifestParser
from app.manifest.validator import ManifestValidator
from app.registry.models import Policy, ToolBinding
from app.sources.base import AgentSource
from app.tools.crm import CRMTool
from app.tools.finance import FinancialTool
from app.tools.market import MarketTool
from app.tools.registry import ToolRegistry


class BuiltinAgentSource(AgentSource):
    """Loads bundled Agent manifests through the standard manifest pipeline."""

    def __init__(self, llm, catalog=None, tool_registry=None):
        self.llm = llm
        self.catalog = catalog or CapabilityCatalog(InMemoryCapabilityRepository())
        self.tool_registry = tool_registry or self._default_tool_registry()

    def load(self, registry):
        self._register_platform_definitions(registry)
        validator = ManifestValidator(
            capability_catalog=self.catalog,
            tool_registry=self.tool_registry,
            policy_registry=registry,
        )
        loader = ManifestLoader(
            parser=ManifestParser(),
            validator=validator,
            registry=registry,
            llm=self.llm,
        )
        agents_path = Path(__file__).resolve().parents[1] / "agents"
        return [loader.load(path) for path in sorted(agents_path.glob("*/agent.yaml"))]

    def _register_platform_definitions(self, registry):
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
        self.catalog.register(CapabilityDefinition(
            capability_id="financial_analysis", name="财务分析",
            description="分析客户收入、负债与现金流", examples=["分析客户财务状况"],
            risk_level="medium", required_permissions=["finance.customer.read"],
            allowed_tools=["financial_query"],
        ))
        self.catalog.register(CapabilityDefinition(
            capability_id="market_analysis", name="市场分析",
            description="分析行业趋势与竞争环境", examples=["分析客户所在市场"],
            risk_level="low", required_permissions=["market.read"], allowed_tools=["market_query"],
        ))
        self.catalog.register(CapabilityDefinition(
            capability_id="risk_assessment", name="风险评估",
            description="综合前序结果评估合作风险", examples=["评估客户合作风险"],
            risk_level="high",
        ))
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
        registry.register_policy(Policy(policy_id="finance_agent_policy", permission_rules=["finance.customer.read"], audit_level="full"))
        registry.register_policy(Policy(policy_id="market_agent_policy", permission_rules=["market.read"], audit_level="full"))
        registry.register_policy(Policy(policy_id="risk_agent_policy", audit_level="full"))
        registry.bind_tool(
            ToolBinding(
                capability_id="customer_analysis",
                tool_name="crm_query",
                required_permission="crm.customer.read",
                risk_level="low",
            )
        )
        registry.bind_tool(ToolBinding("financial_analysis", "financial_query", "finance.customer.read", "medium"))
        registry.bind_tool(ToolBinding("market_analysis", "market_query", "market.read", "low"))

    @staticmethod
    def _default_tool_registry():
        registry = ToolRegistry()
        registry.register("crm_query", CRMTool())
        registry.register("financial_query", FinancialTool())
        registry.register("market_query", MarketTool())
        return registry
