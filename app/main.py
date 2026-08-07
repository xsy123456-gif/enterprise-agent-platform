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
from app.governance.policy import (
    GovernancePolicy,
    InMemoryPolicyRepository,
    PolicyDecisionEngine,
    PolicyRule,
)


from app.llm.factory import create_llm


from app.memory.factory import build_memory_system
from app.memory.ports.authorization import AllowAllMemoryAuthorizationProvider
from app.integrations.memory import (
    PlatformMemoryEventBridge, PlatformMemoryEventSink, RuntimeMemoryAdapter,
)


from app.orchestration.llm_planner import LLMPlanner


from app.orchestration.planner import BasicPlanner


from app.orchestration.supervisor import Supervisor


from app.orchestration.task import Task


from app.orchestration.validator import PlanValidator


from app.permission.rbac import PermissionManager


from app.registry.service import AgentRegistry


from app.registry.storage import InMemoryAgentRepository


from app.runtime.engine import RuntimeEngine


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
    memory_embedding_service=None,
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

    governance_policy = GovernancePolicy(
        policy_id="default_governance",
        name="Default platform governance",
        rules=[
            PolicyRule("system", "create_agent", "*", "allow"),
            PolicyRule("developer", "submit_review", "*", "allow"),
            PolicyRule("admin", "approve_agent", "*", "allow"),
            PolicyRule("admin", "reject_agent", "*", "allow"),
            PolicyRule("admin", "activate_agent", "*", "allow"),
            PolicyRule("admin", "suspend_agent", "*", "allow"),
            PolicyRule("admin", "deprecate_agent", "*", "allow"),
        ],
    )
    governance_engine = PolicyDecisionEngine(InMemoryPolicyRepository())
    governance_engine.register(governance_policy)
    governance_audit = GovernanceAuditSubscriber()
    event_bus.subscribe(governance_audit)

    lifecycle_service = AgentLifecycleService(
        repository=InMemoryLifecycleRepository(),
        event_publisher=EventBusPublisher(event_bus),
        governance_engine=governance_engine,
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

    permission = PermissionManager()



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

        event_bus

    )

    memory_system = build_memory_system(
        repository=memory_repository,
        embedding_service=memory_embedding_service,
        authorization_provider=AllowAllMemoryAuthorizationProvider(),
        event_sink=PlatformMemoryEventSink(event_bus),
        text_model=llm,
        async_mode=False,
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

    runtime.memory_audit = memory_audit
    runtime.lifecycle_service = lifecycle_service
    runtime.governance_policy_engine = governance_engine
    runtime.governance_audit = governance_audit
    runtime.approval_service = ApprovalService(
        InMemoryApprovalRepository(), lifecycle_service,
        event_publisher=EventBusPublisher(event_bus),
    )


    # Control remains in the composition root; Runtime only receives the data-plane adapter.
    return runtime, audit, event_bus



def build_orchestration(
    llm=None, activate_builtin=False, memory_repository=None,
    memory_embedding_service=None,
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
    )

    if activate_builtin:
        lifecycle = runtime.lifecycle_service
        for agent in runtime.agent_registry.list_agents():
            lifecycle.request_review(
                agent.agent_id, agent.version,
                requester="bootstrap", approval_channel="manual",
            )
            lifecycle.approve(agent.agent_id, agent.version, reviewer="bootstrap")
            lifecycle.activate(agent.agent_id, agent.version, operator="bootstrap")

    planner = LLMPlanner(
        llm=llm,
        catalog=capability_catalog,
        validator=PlanValidator(capability_catalog),
        fallback=BasicPlanner(),
    )

    supervisor = Supervisor(
        registry=runtime.agent_registry,
        runtime=runtime
    )

    return (
        planner,
        supervisor,
        audit,
        event_bus,
    )





# =====================================
# Main
# =====================================

def main():

    planner, supervisor, audit, event_bus = build_orchestration(
        activate_builtin=True
    )

    task = Task(
        user_query="分析客户A的合作风险"
    )

    plan = planner.plan(task)

    result = supervisor.execute(
        plan=plan,
        user_id="sales_001",
        role="sales"
    )

    print(
        "\n最终结果:"
    )


    print(
        result.output
    )



    print(
        "\n审计记录:"
    )


    print(
        audit.logs
    )



    print(
        "\n事件记录:"
    )


    print(
        event_bus.events
    )





if __name__ == "__main__":

    main()
