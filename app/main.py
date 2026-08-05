from app.runtime.executor import AgentExecutor
from app.runtime.tool_runner import ToolRunner

from app.runtime.context import AgentContext

from app.agents.sales import SalesAgent

from app.llm.factory import create_llm

from app.tools.crm import CRMTool
from app.tools.registry import ToolRegistry

from app.permission.rbac import RBAC
from app.audit.logger import AuditLogger

from app.events.bus import EventBus
from app.events.subscriber import EventSubscriber
from app.memory.worker import MemoryWorker

from app.memory.storage import MemoryStorage
from app.memory.service import MemoryService



def main():

    # =========================
    # LLM Layer
    # =========================

    llm = create_llm()


    # =========================
    # Agent Layer
    # =========================

    agent = SalesAgent(
        llm
    )


    # =========================
    # Tool Layer
    # =========================

    registry = ToolRegistry()

    crm_tool = CRMTool()

    registry.register(
        crm_tool
    )


    # =========================
    # Permission
    # =========================

    permission = RBAC()



    # =========================
    # Audit
    # =========================

    audit = AuditLogger()



    # =========================
    # Memory
    # =========================

    memory_storage = MemoryStorage()

    memory = MemoryService(
        memory_storage
    )



    # =========================
    # Event System
    # =========================

    event_bus = EventBus()

    subscriber = EventSubscriber()

    memory_worker = MemoryWorker(
        memory
    )


    subscriber.subscribe(
        "tool_completed",
        memory_worker.process
    )


    event_bus.subscribe(
        subscriber
    )



    # =========================
    # Runtime Tool Runner
    # =========================

    tool_runner = ToolRunner(

        registry,

        permission,

        audit,

        event_bus

    )



    # =========================
    # Executor
    # =========================

    executor = AgentExecutor(

        agent,

        tool_runner

    )



    # =========================
    # Agent State
    # =========================

    context = AgentContext(

        task="准备客户A拜访资料",

        user_id="sales_001",

        role="sales_rep",

	agent_name="sales_agent"

    )



    # =========================
    # Run
    # =========================

    result = executor.run(
        context
    )



    print("\n最终结果:")
    print(result)



    print("\n审计记录:")

    print(
        audit.get_logs()
    )



    print("\n事件记录:")

    print(
        event_bus.get_events()
    )



if __name__ == "__main__":

    main()
