from app.audit.logger import AuditLogger
from app.audit.memory import MemoryAuditSubscriber
from app.audit.governance import GovernanceAuditSubscriber


from app.capabilities.catalog import CapabilityCatalog


from app.capabilities.repository import InMemoryCapabilityRepository


from app.sources.factory import AgentSourceFactory


from app.events.bus import EventBus


from app.governance.events import EventBusPublisher


from app.governance.repository import InMemoryLifecycleRepository


from app.governance.service import AgentLifecycleService
from app.governance.approval.repository import InMemoryApprovalRepository
from app.governance.approval.service import ApprovalService


from app.llm.factory import create_llm


from app.memory.factory import build_memory_system
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from app.integrations.memory import (
    PlatformMemoryEventBridge, PlatformMemoryEventSink, RuntimeMemoryAdapter,
)


from app.orchestration.llm_planner import LLMPlanner


from app.orchestration.planner import BasicPlanner


from app.orchestration.supervisor import Supervisor


from app.orchestration.validator import PlanValidator


from app.registry.service import AgentRegistry


from app.registry.storage import InMemoryAgentRepository


from app.runtime.engine import RuntimeEngine
from app.runtime.dispatcher import RuntimeDispatcher
from app.storage.providers.memory import InMemoryEventStore, InMemoryTraceRepository
from app.runtime.trace import AsyncTraceConsumer, TraceAssembler, TraceQueryService


from app.runtime.tool_runner import ToolRunner


from app.tools.crm import CRMTool
from app.tools.finance import FinancialTool
from app.tools.market import MarketTool


from app.tools.registry import ToolRegistry



# =====================================
# Build Runtime
# =====================================

def build_runtime(
    llm=None, capability_catalog=None, memory_repository=None,
    memory_embedding_service=None, security=None,
):


    # -----------------------------
    # LLM
    # -----------------------------

    if llm is None:
        llm = create_llm()

    if capability_catalog is None:
        capability_catalog = CapabilityCatalog(
            InMemoryCapabilityRepository()
        )

    event_bus = EventBus()

    governance_audit = GovernanceAuditSubscriber()
    event_bus.subscribe(governance_audit)

    # Development/test compatibility: without a wired security integration,
    # lifecycle authorization defaults to allow-all.  Production always wires
    # security (build_application), so this never applies there.
    if security is None:
        class _DevAllowAllAuthorization:
            def authorize(self, principal, action, agent_id, version):
                return True

        lifecycle_authorization = _DevAllowAllAuthorization()
    else:
        lifecycle_authorization = security.lifecycle_authorization

    lifecycle_service = AgentLifecycleService(
        repository=InMemoryLifecycleRepository(),
        event_publisher=EventBusPublisher(event_bus),
        authorization=lifecycle_authorization,
    )



    # -----------------------------
    # Tool Registry
    # -----------------------------

    tool_registry = ToolRegistry()

    tool_registry.register(
        "crm_query",
        CRMTool()
    )
    tool_registry.register("financial_query", FinancialTool())
    tool_registry.register("market_query", MarketTool())

    # -----------------------------
    # Agent Registry
    # -----------------------------

    agent_registry = AgentRegistry(
        InMemoryAgentRepository(),
        capability_catalog=capability_catalog
    )
    agent_registry.attach_lifecycle_service(lifecycle_service)

    source_factory = AgentSourceFactory(
        llm=llm,
        catalog=capability_catalog,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
    )

    source = source_factory.create({"type": "builtin"})

    source.load(agent_registry)



    # -----------------------------
    # Permission
    # -----------------------------

    # User authorization is handled by ExecutionSecurityGate (Permission ->
    # Governance) at the tool invocation boundary.  ToolRunner keeps only
    # structural constraints here.
    from app.integrations.security.tools.structural import StructuralPermission

    permission = StructuralPermission()



    # -----------------------------
    # Audit
    # -----------------------------

    audit = AuditLogger()



    # -----------------------------
    # Tool Runner
    # -----------------------------

    tool_runner = ToolRunner(

        tool_registry,

        permission,

        audit,

        event_bus,
        agent_registry=agent_registry,

    )

    memory_system = build_memory_system(
        repository=memory_repository,
        embedding_service=memory_embedding_service,
        authorization_provider=AllowAllMemoryAuthorizationProvider(),
        event_sink=PlatformMemoryEventSink(event_bus),
        text_model=llm,
    )
    memory_adapter = RuntimeMemoryAdapter(memory_system)
    memory_bridge = PlatformMemoryEventBridge(memory_system)
    event_bus.subscribe(memory_bridge)
    memory_audit = MemoryAuditSubscriber()
    event_bus.subscribe(memory_audit)



    # -----------------------------
    # Runtime Engine
    # -----------------------------

    runtime = RuntimeEngine(
        agent_registry=agent_registry,
        tool_runner=tool_runner,
        max_steps=10,
        memory_adapter=memory_adapter,

    )

    # Expose the composed Memory subsystem to the composition root without
    # making Runtime own its lifecycle.
    runtime.memory_system = memory_system

    runtime.memory_audit = memory_audit
    runtime.lifecycle_service = lifecycle_service
    runtime.governance_audit = governance_audit
    runtime.approval_service = ApprovalService(
        InMemoryApprovalRepository(), lifecycle_service,
        event_publisher=EventBusPublisher(event_bus),
    )


    # Control remains in the composition root; Runtime only receives the data-plane adapter.
    return runtime, audit, event_bus



def build_orchestration(
    llm=None, activate_builtin=False, memory_repository=None,
    memory_embedding_service=None, security=None,
):

    if llm is None:
        llm = create_llm()

    capability_catalog = CapabilityCatalog(
        InMemoryCapabilityRepository()
    )

    runtime, audit, event_bus = build_runtime(
        llm=llm,
        capability_catalog=capability_catalog,
        memory_repository=memory_repository,
        memory_embedding_service=memory_embedding_service,
        security=security,
    )

    if activate_builtin:
        from app.integrations.security.models.trusted_principal import TrustedPrincipal

        bootstrap = TrustedPrincipal(principal_id="platform.bootstrap", source="system")
        lifecycle = runtime.lifecycle_service
        for agent in runtime.agent_registry.list_agents():
            lifecycle.request_review(
                agent.agent_id, agent.version,
                principal=bootstrap, approval_channel="manual",
            )
            lifecycle.approve(agent.agent_id, agent.version, principal=bootstrap)
            lifecycle.activate(agent.agent_id, agent.version, principal=bootstrap)

    planner = LLMPlanner(
        llm=llm,
        catalog=capability_catalog,
        validator=PlanValidator(capability_catalog),
        fallback=BasicPlanner(),
    )

    runtime_dispatcher = RuntimeDispatcher.from_runtime_engine(
        runtime, runtime.agent_registry, event_bus=event_bus,
        governance_gate=getattr(security, "tool_gate", None),
    )
    runtime_dispatcher.event_bus = event_bus
    runtime_dispatcher.event_store = InMemoryEventStore()
    trace_repository = InMemoryTraceRepository()
    trace_consumer = AsyncTraceConsumer(TraceAssembler(trace_repository))
    event_bus.subscribe(trace_consumer)
    runtime_dispatcher.trace_repository = trace_repository
    runtime_dispatcher.trace_query = TraceQueryService(trace_repository)
    runtime_dispatcher.trace_consumer = trace_consumer

    supervisor = Supervisor(
        registry=runtime.agent_registry,
        runtime=runtime_dispatcher,
    )

    return (
        planner,
        supervisor,
        audit,
        event_bus,
    )


def build_application(environment=None, **kwargs):
    """Create an explicit environment-aware application container.

    Existing ``build_orchestration`` remains the compatibility entrypoint; the
    container is the preferred lifecycle boundary for new callers.
    """
    from app.composition import create_application
    from app.identity import build_identity
    from app.integrations.security import build_security_integration
    from app.permission import build_permission
    from app.runtime.governance.gate import AllowAllGovernancePolicy, GovernanceGate

    identity = build_identity()
    permission = build_permission()
    permission.runtime.start()
    security = build_security_integration(
        identity_service=identity.service,
        permission_service=permission.service,
        governance_gate=GovernanceGate(AllowAllGovernancePolicy()),
    )

    planner, supervisor, audit, event_bus = build_orchestration(
        security=security, **kwargs
    )
    runtime = supervisor.runtime
    return create_application(
        environment=environment,
        runtime=runtime,
        memory=getattr(runtime, "memory_system", None),
        governance=security,
        trace=getattr(runtime, "trace_consumer", None),
        execution=getattr(runtime, "execution_manager", None),
        registry=runtime.agent_registry,
        event_bus=event_bus,
        audit=audit,
        planner=planner,
        supervisor=supervisor,
        identity=identity,
        permission=permission,
        security=security,
    )
