import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.main import build_orchestration, main as application_main
from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.orchestration.llm_planner import LLMPlanner, LLMPlannerError
from app.orchestration.models import ExecutionStatus, StepStatus
from app.orchestration.plan import TaskPlan
from app.orchestration.planner import BasicPlanner
from app.orchestration.supervisor import Supervisor
from app.orchestration.task import Task, TaskStep
from app.orchestration.validator import PlanValidationError, PlanValidator
from app.registry.models import Agent, AgentStatus
from app.registry.service import AgentRegistry
from app.registry.storage import InMemoryAgentRepository


class StubAgent:
    def think(self, state):
        raise AssertionError("Supervisor must not execute an Agent directly")


class RecordingRuntime:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def run(self, state, agent_id=None, version=None):
        self.calls.append(
            {
                "state": state,
                "agent_id": agent_id,
                "version": version,
            }
        )
        if self.fail:
            raise RuntimeError("runtime failed")
        return f"completed by {agent_id}:{version}"


class ToolCallingStubLLM:
    def __init__(self):
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return (
                '{"type":"tool","tool":"crm_query",'
                '"input":"customer_A"}'
            )
        return '{"type":"finish","output":"visit prepared"}'


class PlannerAndAgentStubLLM(ToolCallingStubLLM):
    def chat(self, messages, **kwargs):
        if "任务规划器" in messages[0].get("content", ""):
            return (
                '{"goal":"准备客户拜访资料",'
                '"steps":['
                '{"step_id":"1","capability":"customer_analysis",'
                '"dependencies":[]},'
                '{"step_id":"2","capability":"visit_prepare",'
                '"dependencies":["1"]}'
                ']}'
            )
        return super().chat(messages, **kwargs)


class CapturingPlannerLLM:
    def __init__(self):
        self.messages = None

    def chat(self, messages, **kwargs):
        self.messages = messages
        return (
            '{"goal":"Analyze", "steps":['
            '{"step_id":"1","capability":"customer_analysis",'
            '"dependencies":[]}]}'
        )


class OrchestrationTest(unittest.TestCase):
    def setUp(self):
        self.registry = AgentRegistry(InMemoryAgentRepository())

    def register_agent(self, agent_id, version, capabilities):
        definition = Agent(
            agent_id=agent_id,
            name=agent_id,
            version=version,
            description="test agent",
            owner="test",
            status=AgentStatus.ACTIVE,
            capabilities=capabilities,
            instance=StubAgent(),
        )
        self.registry.register(definition)
        return definition

    def test_planner_outputs_capabilities_not_agents(self):
        plan = BasicPlanner().plan(Task(user_query="准备客户A拜访资料"))

        self.assertEqual(
            ["customer_analysis", "visit_prepare"],
            [step.capability for step in plan.steps],
        )
        self.assertEqual([], plan.steps[0].dependencies)
        self.assertEqual(["1"], plan.steps[1].dependencies)
        self.assertNotIn("agent", plan.to_dict())
        self.assertTrue(
            all("agent" not in step for step in plan.to_dict()["steps"])
        )

    def test_llm_planner_validates_capability_plan(self):
        catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        catalog.register(
            CapabilityDefinition(
                capability_id="customer_analysis",
                name="Customer analysis",
                description="Analyze customers",
            )
        )
        llm = type(
            "LLM",
            (),
            {
                "chat": lambda self, messages, **kwargs: (
                    '{"goal":"Analyze", "steps":['
                    '{"step_id":"1","capability":"customer_analysis",'
                    '"dependencies":[]}]}'
                )
            },
        )()

        plan = LLMPlanner(
            llm=llm,
            catalog=catalog,
            validator=PlanValidator(catalog),
        ).plan(Task(user_query="Analyze customer"))

        self.assertEqual("customer_analysis", plan.steps[0].capability)

    def test_llm_planner_receives_catalog_context_without_tool_binding(self):
        catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        catalog.register(
            CapabilityDefinition(
                capability_id="customer_analysis",
                name="Customer analysis",
                description="Analyze customers",
                examples=["query customer profile"],
                allowed_tools=["crm_query"],
            )
        )
        llm = CapturingPlannerLLM()

        LLMPlanner(
            llm=llm,
            catalog=catalog,
            validator=PlanValidator(catalog),
        ).plan(Task(user_query="Analyze customer"))

        prompt = llm.messages[0]["content"]
        self.assertIn("customer_analysis", prompt)
        self.assertIn("Analyze customers", prompt)
        self.assertNotIn("crm_query", prompt)

    def test_validator_rejects_unknown_capability_and_agent_fields(self):
        validator = PlanValidator(self.registry)
        task = Task(user_query="unknown")

        with self.assertRaises(PlanValidationError):
            validator.validate(
                task,
                {
                    "goal": "unknown",
                    "steps": [
                        {
                            "step_id": "1",
                            "capability": "finance_salary_query",
                        }
                    ],
                },
            )

        with self.assertRaises(PlanValidationError):
            validator.validate(
                task,
                {
                    "goal": "bad",
                    "agent_id": "sales_agent",
                    "steps": [],
                },
            )

    def test_llm_planner_uses_fallback_only_when_llm_unavailable(self):
        class BrokenLLM:
            def chat(self, messages, **kwargs):
                raise ConnectionError("offline")

        fallback = BasicPlanner()
        catalog = CapabilityCatalog(InMemoryCapabilityRepository())
        planner = LLMPlanner(
            llm=BrokenLLM(),
            catalog=catalog,
            validator=PlanValidator(catalog),
            fallback=fallback,
        )
        plan = planner.plan(Task(user_query="arbitrary task"))
        self.assertEqual("customer_analysis", plan.steps[0].capability)

        with self.assertRaises(LLMPlannerError):
            LLMPlanner(
                llm=BrokenLLM(),
                catalog=catalog,
                validator=PlanValidator(catalog),
            ).plan(Task(user_query="arbitrary task"))

    def test_supervisor_resolves_capability_and_calls_runtime(self):
        self.register_agent("analysis_agent", "1.0", ["customer_analysis"])
        runtime = RecordingRuntime()
        supervisor = Supervisor(self.registry, runtime)
        plan = TaskPlan(
            task_id="task-1",
            goal="analyze customer",
            steps=[TaskStep("1", "customer_analysis")],
        )

        result = supervisor.execute(plan, user_id="user-1", role="sales")

        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual("analysis_agent", runtime.calls[0]["agent_id"])
        self.assertEqual("1.0", runtime.calls[0]["version"])
        self.assertEqual(StepStatus.COMPLETED, plan.steps[0].status)
        state = supervisor.get_execution(result.execution_id)
        self.assertEqual(ExecutionStatus.COMPLETED, state.status)

    def test_registry_selects_latest_capable_agent_version(self):
        self.register_agent("analysis_agent", "1.0", ["customer_analysis"])
        latest = self.register_agent(
            "analysis_agent", "1.2", ["customer_analysis"]
        )

        self.assertIs(
            latest,
            self.registry.resolve_by_capability("customer_analysis"),
        )

    def test_dependencies_are_executed_in_order(self):
        self.register_agent("worker", "1.0", ["first", "second"])
        runtime = RecordingRuntime()
        supervisor = Supervisor(self.registry, runtime)
        plan = TaskPlan(
            task_id="task-2",
            goal="ordered work",
            steps=[
                TaskStep("1", "first"),
                TaskStep("2", "second", dependencies=["1"]),
            ],
        )

        result = supervisor.execute(plan, user_id="user-1", role="sales")

        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual(2, len(runtime.calls))
        self.assertIn("Previous results: {}", runtime.calls[0]["state"].task)
        self.assertIn("completed by worker:1.0", runtime.calls[1]["state"].task)

    def test_missing_capability_requests_replan_without_runtime_call(self):
        runtime = RecordingRuntime()
        supervisor = Supervisor(self.registry, runtime)
        plan = TaskPlan(
            task_id="task-3",
            goal="unsupported work",
            steps=[TaskStep("1", "unsupported")],
        )

        result = supervisor.execute(plan, user_id="user-1", role="sales")

        self.assertEqual(ExecutionStatus.BLOCKED, result.status)
        self.assertTrue(result.replan_required)
        self.assertEqual([], runtime.calls)

    def test_runtime_failure_is_recorded_and_not_retried(self):
        self.register_agent("worker", "1.0", ["first", "second"])
        runtime = RecordingRuntime(fail=True)
        supervisor = Supervisor(self.registry, runtime)
        plan = TaskPlan(
            task_id="task-4",
            goal="failing work",
            steps=[
                TaskStep("1", "first"),
                TaskStep("2", "second", dependencies=["1"]),
            ],
        )

        result = supervisor.execute(plan, user_id="user-1", role="sales")

        self.assertEqual(ExecutionStatus.FAILED, result.status)
        self.assertTrue(result.replan_required)
        self.assertEqual(1, len(runtime.calls))
        self.assertEqual(StepStatus.FAILED, result.steps[0].status)
        self.assertEqual(StepStatus.BLOCKED, result.steps[1].status)

    def test_application_orchestration_preserves_runtime_services(self):
        llm = PlannerAndAgentStubLLM()
        with patch("app.main.create_llm", return_value=llm):
            planner, supervisor, audit, event_bus = build_orchestration()

        plan = planner.plan(Task(user_query="准备客户A拜访资料"))
        with redirect_stdout(StringIO()):
            result = supervisor.execute(plan, "sales_001", "sales")

        self.assertEqual(ExecutionStatus.COMPLETED, result.status)
        self.assertEqual("visit prepared", result.output)
        self.assertEqual("crm_query", audit.logs[0]["tool"])
        self.assertIn(
            "tool_completed",
            [event.event_type for event in event_bus.events],
        )

    def test_main_uses_orchestration_without_external_agent_selection(self):
        output = StringIO()
        with patch("app.main.create_llm", return_value=PlannerAndAgentStubLLM()):
            with redirect_stdout(output):
                application_main()

        self.assertIn("visit prepared", output.getvalue())


if __name__ == "__main__":
    unittest.main()
