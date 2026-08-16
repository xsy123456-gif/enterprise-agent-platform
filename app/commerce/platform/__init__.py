"""Commerce tool-surface platform integration.

Wires the seven governed read tools into the existing Platform: Capability
Catalog registrations, ToolRegistry registrations, Capability -> ToolBinding,
and a production ``FactQueryExecutorPort`` that goes through
Capability -> ToolBinding -> ToolRunner -> Tool (never the QueryService /
Repository directly).  The STRICT scope and permission checks happen inside the
tool and the governance gate before any canonical query.

Typed errors (PERMISSION_DENIED / INVALID_REQUEST / SUBJECT_NOT_FOUND / ...) are
propagated as ``FactQueryResult.error`` — never folded into data insufficiency.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field

from app.audit.logger import AuditLogger
from app.capabilities.models import CapabilityDefinition
from app.commerce.diagnostics.plans.ports import (
    FACT_QUALITY_INSUFFICIENT,
    FACT_QUALITY_VALID,
    FactQueryExecutorPort,
    FactQueryResult,
    FactQuerySpec,
)
from app.commerce.tools import build_commerce_tools
from app.commerce.trusted_context import reset_trusted_context, set_trusted_context
from app.integrations.security.tools.structural import StructuralPermission
from app.registry.models import ToolBinding
from app.runtime.tool_runner import ToolRunner
from app.tools.models import ToolCallRequest
from app.tools.registry import ToolRegistry

COMMERCE_CAPABILITIES = (
    CapabilityDefinition(
        capability_id="commerce.store.read", name="Store Read",
        description="读取店铺身份与元数据", risk_level="low",
        required_permissions=["execute"], allowed_tools=["store.get"],
    ),
    CapabilityDefinition(
        capability_id="commerce.catalog.read", name="Catalog Read",
        description="读取商品/商品SKU/Listing/ListingItem", risk_level="low",
        required_permissions=["execute"], allowed_tools=["catalog.query"],
    ),
    CapabilityDefinition(
        capability_id="commerce.metrics.read", name="Metrics Read",
        description="读取 SOURCE/AGGREGATED 指标事实", risk_level="low",
        required_permissions=["execute"], allowed_tools=["metric.query"],
    ),
    CapabilityDefinition(
        capability_id="commerce.inventory.read", name="Inventory Read",
        description="读取库存快照事实", risk_level="low",
        required_permissions=["execute"], allowed_tools=["inventory.query"],
    ),
    CapabilityDefinition(
        capability_id="commerce.review.read", name="Review Read",
        description="读取评价/评价洞察", risk_level="low",
        required_permissions=["execute"], allowed_tools=["review.query"],
    ),
    CapabilityDefinition(
        capability_id="commerce.review_insight.read", name="Review Insight Read",
        description="读取评价洞察 AI 事实", risk_level="low",
        required_permissions=["execute"], allowed_tools=["review_insight.query"],
    ),
    CapabilityDefinition(
        capability_id="commerce.advertising.read", name="Advertising Read",
        description="读取广告实体", risk_level="low",
        required_permissions=["execute"], allowed_tools=["advertising.query"],
    ),
)

COMMERCE_BINDINGS = tuple(
    ToolBinding(
        capability_id=cap.capability_id, tool_name=cap.allowed_tools[0],
        required_permission="execute", risk_level=cap.risk_level,
    )
    for cap in COMMERCE_CAPABILITIES
)

CAPABILITY_TOOL = {
    "commerce.store.read": "store.get",
    "commerce.catalog.read": "catalog.query",
    "commerce.metrics.read": "metric.query",
    "commerce.inventory.read": "inventory.query",
    "commerce.review.read": "review.query",
    "commerce.review_insight.read": "review_insight.query",
    "commerce.advertising.read": "advertising.query",
}

_QUALITY_MAP = {
    "VALID": FACT_QUALITY_VALID,
    "PARTIAL": "PARTIAL",
    "STALE": "PARTIAL",
    "INSUFFICIENT": FACT_QUALITY_INSUFFICIENT,
    "INVALID": FACT_QUALITY_INSUFFICIENT,
}

_FRESHNESS_MAP = {
    "FRESH": "FRESH",
    "REFRESHED": "FRESH",
    "STALE": "STALE",
    "UNKNOWN": "UNKNOWN",
}

_audit_context: ContextVar = ContextVar("commerce_audit_context", default=None)


class CommerceAuditLogger(AuditLogger):
    """Audit logger that enriches every record with the current request context
    (capability / principal / tenant / trace / execution / subject)."""

    def record(self, user, agent, tool, action, detail):
        item = super().record(user, agent, tool, action, detail)
        ctx = _audit_context.get()
        if ctx:
            item.update(ctx)
        return item


def set_audit_context(ctx):
    return _audit_context.set(ctx)


def reset_audit_context(token):
    _audit_context.reset(token)


def _is_tool_error(output):
    if isinstance(output, dict):
        return bool(output.get("code")) and "category" in output
    return bool(getattr(output, "code", None)) and bool(getattr(output, "category", None))


class ToolRunnerFactQueryExecutor(FactQueryExecutorPort):
    """Production FactQueryExecutorPort: Capability -> ToolRunner -> Tool.

    It never calls CommerceQueryService / Repository directly; the governed
    read tools do that behind the STRICT scope and permission checks.  Tool
    errors are propagated as ``FactQueryResult.error`` (typed), never folded
    into INSUFFICIENT.
    """

    def __init__(self, tool_runner, governance_gate=None, audit=None,
                 capability_tool=None, agent_id="commerce.read"):
        self.tool_runner = tool_runner
        self.governance_gate = governance_gate
        self.audit = audit
        self.capability_tool = capability_tool or CAPABILITY_TOOL
        self.agent_id = agent_id

    def execute(self, spec: FactQuerySpec, trusted_context):
        tool_name = self.capability_tool.get(spec.capability)
        if tool_name is None:
            return FactQueryResult(query_id=spec.query_id, records=(),
                                   error="PERMISSION_DENIED")
        request = ToolCallRequest(
            tool_name=tool_name,
            arguments=self._arguments(spec),
            trace_id=trusted_context.trace_id or spec.query_id,
            execution_id=trusted_context.execution_id or spec.query_id,
            agent_id=self.agent_id,
            user_id=trusted_context.principal_id,
            tenant_id=trusted_context.tenant_id,
            capability=spec.capability,
        )
        audit_ctx = {
            "capability": spec.capability,
            "tool": tool_name,
            "principal_id": trusted_context.principal_id,
            "tenant_id": trusted_context.tenant_id,
            "trace_id": request.trace_id,
            "execution_id": request.execution_id,
            "subject": spec.subject.to_dict() if spec.subject else None,
        }
        token = set_trusted_context(trusted_context)
        audit_token = set_audit_context(audit_ctx)
        try:
            if self.governance_gate is not None:
                allowed, _decision = self.governance_gate.check(request)
                if not allowed:
                    if self.audit is not None:
                        self.audit.record(
                            user=request.user_id, agent=request.agent_id,
                            tool=request.tool_name, action="deny",
                            detail=request.arguments,
                        )
                    return FactQueryResult(query_id=spec.query_id, records=(),
                                           error="PERMISSION_DENIED")
            result = self.tool_runner.execute(request)
        finally:
            reset_audit_context(audit_token)
            reset_trusted_context(token)
        if not result.success:
            return FactQueryResult(query_id=spec.query_id, records=(),
                                   error="INTERNAL_ERROR")
        output = result.output
        if _is_tool_error(output):
            code = output.get("code") if isinstance(output, dict) else output.code
            return FactQueryResult(query_id=spec.query_id, records=(), error=code)
        return self._to_fact_result(spec, output)

    @staticmethod
    def _arguments(spec):
        args = dict(spec.params or {})
        if spec.subject is not None:
            args.setdefault("subject_type", spec.subject.type)
            args.setdefault("subject_id", spec.subject.id)
            if spec.subject.type == "STORE":
                args.setdefault("store_id", spec.subject.id)
        if spec.resource and spec.capability == "commerce.metrics.read":
            args.setdefault("metric_names", [spec.resource])
        return args

    @staticmethod
    def _to_fact_result(spec, query_result):
        records = []
        for item in getattr(query_result, "data", ()) or ():
            if isinstance(item, dict):
                records.append(dict(item))
            elif hasattr(item, "to_dict"):
                records.append(item.to_dict())
        quality = _QUALITY_MAP.get(
            getattr(query_result.quality, "status", "VALID"), FACT_QUALITY_VALID
        )
        freshness = _FRESHNESS_MAP.get(
            getattr(query_result.freshness, "status", "UNKNOWN"), "UNKNOWN"
        )
        provenance = None
        if getattr(query_result, "provenance", None) is not None:
            provenance = query_result.provenance.to_dict()
        return FactQueryResult(
            query_id=spec.query_id, records=tuple(records),
            quality=quality, freshness=freshness, provenance=provenance,
        )


@dataclass
class CommerceToolSurface:
    capabilities: tuple = field(default_factory=tuple)
    bindings: tuple = field(default_factory=tuple)
    tools: dict = field(default_factory=dict)
    tool_runner: object = None
    fact_executor: object = None
    audit: object = None
    event_bus: object = None


def build_commerce_tool_surface(query_service, metric_registry=None,
                                governance_gate=None, event_bus=None,
                                agent_registry=None):
    """Register the seven capabilities + tools + bindings and wire the surface."""
    tools = build_commerce_tools(query_service, metric_registry=metric_registry)
    tool_registry = ToolRegistry()
    for name, tool in tools.items():
        tool_registry.register(name, tool)

    audit = CommerceAuditLogger()
    tool_runner = ToolRunner(
        tool_registry, StructuralPermission(), audit,
        event_bus or _null_event_bus(), agent_registry=agent_registry,
    )
    if agent_registry is not None:
        for binding in COMMERCE_BINDINGS:
            agent_registry.bind_tool(binding)

    fact_executor = ToolRunnerFactQueryExecutor(
        tool_runner, governance_gate=governance_gate, audit=audit,
        capability_tool=CAPABILITY_TOOL,
    )
    return CommerceToolSurface(
        capabilities=COMMERCE_CAPABILITIES,
        bindings=COMMERCE_BINDINGS,
        tools=tools,
        tool_runner=tool_runner,
        fact_executor=fact_executor,
        audit=audit,
        event_bus=event_bus,
    )


class _NullEventBus:
    def publish(self, event):
        return None


def _null_event_bus():
    return _NullEventBus()


__all__ = [
    "COMMERCE_CAPABILITIES",
    "COMMERCE_BINDINGS",
    "CAPABILITY_TOOL",
    "ToolRunnerFactQueryExecutor",
    "CommerceToolSurface",
    "CommerceAuditLogger",
    "build_commerce_tool_surface",
]
