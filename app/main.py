from app.audit.logger import AuditLogger


from app.bootstrap.agents import register_builtin_agents


from app.events.bus import EventBus


from app.llm.factory import create_llm


from app.permission.rbac import PermissionManager


from app.registry.service import AgentRegistry


from app.registry.storage import InMemoryAgentRepository


from app.runtime.context import AgentContext


from app.runtime.engine import RuntimeEngine


from app.runtime.tool_runner import ToolRunner


from app.tools.crm import CRMTool


from app.tools.registry import ToolRegistry



# =====================================
# Build Runtime
# =====================================

def build_runtime():


    # -----------------------------
    # LLM
    # -----------------------------

    llm = create_llm()



    # -----------------------------
    # Agent Registry
    # -----------------------------

    agent_registry = AgentRegistry(
        InMemoryAgentRepository()
    )


    register_builtin_agents(
        agent_registry,
        llm
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
    # Permission
    # -----------------------------

    permission = PermissionManager()



    # -----------------------------
    # Audit
    # -----------------------------

    audit = AuditLogger()



    # -----------------------------
    # Event
    # -----------------------------

    event_bus = EventBus()



    # -----------------------------
    # Tool Runner
    # -----------------------------

    tool_runner = ToolRunner(

        tool_registry,

        permission,

        audit,

        event_bus

    )



    # -----------------------------
    # Runtime Engine
    # -----------------------------

    runtime = RuntimeEngine(
        agent_registry=agent_registry,
        tool_runner=tool_runner,
        max_steps=10

    )


    return (
        runtime,
        audit,
        event_bus
    )





# =====================================
# Main
# =====================================

def main():


    runtime, audit, event_bus = build_runtime()



    state = AgentContext(

        task="准备客户A拜访资料",

        user_id="sales_001",

        role="sales",

        agent_name="sales_agent"

    )



    result = runtime.run(

        state

    )



    print(
        "\n最终结果:"
    )


    print(
        result
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
