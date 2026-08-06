from app.audit.logger import AuditLogger


from app.capabilities.catalog import CapabilityCatalog


from app.capabilities.repository import InMemoryCapabilityRepository


from app.sources.factory import AgentSourceFactory


from app.events.bus import EventBus


from app.governance.events import EventBusPublisher


from app.governance.repository import InMemoryLifecycleRepository


from app.governance.service import AgentLifecycleService


from app.llm.factory import create_llm


from app.memory.policy import MemoryGuard


from app.memory.service import MemoryService


from app.memory.storage import MemoryStorage


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


from app.tools.registry import ToolRegistry



# =====================================
# Build Runtime
# =====================================

def build_runtime(llm=None, capability_catalog=None):


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

    lifecycle_service = AgentLifecycleService(
        repository=InMemoryLifecycleRepository(),
        event_publisher=EventBusPublisher(event_bus),
    )



    # -----------------------------
    # Tool Registry
    # -----------------------------

    tool_registry = ToolRegistry()

    tool_registry.register(
        "crm_query",
        CRMTool()
    )

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

    memory_service = MemoryService(MemoryStorage())

    memory_guard = MemoryGuard(memory_service=memory_service)



    # -----------------------------
    # Runtime Engine
    # -----------------------------

    runtime = RuntimeEngine(
        agent_registry=agent_registry,
        tool_runner=tool_runner,
        max_steps=10,
        memory_guard=memory_guard,

    )

    runtime.memory_service = memory_service
    runtime.lifecycle_service = lifecycle_service


    return (
        runtime,
        audit,
        event_bus
    )



def build_orchestration(llm=None, activate_builtin=False):

    if llm is None:
        llm = create_llm()

    capability_catalog = CapabilityCatalog(
        InMemoryCapabilityRepository()
    )

    runtime, audit, event_bus = build_runtime(
        llm=llm,
        capability_catalog=capability_catalog,
    )

    if activate_builtin:
        lifecycle = runtime.lifecycle_service
        lifecycle.request_review(
            "sales_agent",
            "0.2",
            requester="bootstrap",
            approval_channel="manual",
        )
        lifecycle.approve("sales_agent", "0.2", reviewer="bootstrap")
        lifecycle.activate("sales_agent", "0.2", operator="bootstrap")

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
        event_bus
    )





# =====================================
# Main
# =====================================

def main():

    planner, supervisor, audit, event_bus = build_orchestration(
        activate_builtin=True
    )

    task = Task(
        user_query="准备客户A拜访资料"
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
