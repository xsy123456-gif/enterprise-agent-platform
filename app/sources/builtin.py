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
        manifest_path = (
            Path(__file__).resolve().parents[1]
            / "agents"
            / "sales_agent"
            / "agent.yaml"
        )
        return [loader.load(manifest_path)]

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

    @staticmethod
    def _default_tool_registry():
        registry = ToolRegistry()
        registry.register("crm_query", CRMTool())
        return registry
