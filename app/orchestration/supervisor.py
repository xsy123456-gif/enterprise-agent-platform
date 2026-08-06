from app.orchestration.models import (
    ExecutionStatus,
    StepResult,
    StepStatus,
    SupervisionResult,
)
from app.orchestration.state import ExecutionState, InMemoryExecutionStateStore
from app.orchestration.scheduler import ParallelTaskScheduler
from app.orchestration.aggregation import ResultAggregator
from app.runtime.context import AgentContext


class AgentResolutionError(Exception):
    pass


class Supervisor:
    """Schedules capability tasks through Registry and Agent Runtime."""

    def __init__(
        self,
        registry,
        runtime,
        state_store=None,
        scheduler=None,
        aggregator=None,
    ):
        self.registry = registry
        self.runtime = runtime
        self.state_store = state_store or InMemoryExecutionStateStore()
        self.scheduler = scheduler or ParallelTaskScheduler()
        self.aggregator = aggregator or ResultAggregator()

    def execute(self, plan, user_id, role):
        if any(step.status != StepStatus.PENDING for step in plan.steps):
            raise ValueError("Supervisor requires a new plan with pending steps")

        state = ExecutionState.from_plan(plan)
        state.start()
        self.state_store.save(state)

        while self._pending_steps(plan):
            ready_steps = self._ready_steps(plan)
            if not ready_steps:
                self._block_pending_steps(
                    plan,
                    state,
                    "No executable step; dependencies are not satisfied",
                )
                break

            jobs = []
            steps_by_id = {step.step_id: step for step in ready_steps}
            job_calls = {}
            executable_steps = []
            for step in ready_steps:
                try:
                    agent = self._resolve_agent(step.capability)
                except AgentResolutionError as error:
                    state.block_step(step.step_id, error)
                    step.status = StepStatus.BLOCKED
                    continue
                state.start_step(step.step_id, agent.agent_id, agent.version)
                step.status = StepStatus.RUNNING
                context = self._build_context(plan, step, state, user_id, role, agent)
                executable_steps.append(step)
                job_calls[step.step_id] = (
                    lambda context=context, agent=agent: self.runtime.run(
                        context, agent_id=agent.agent_id, version=agent.version,
                    )
                )
            jobs = self.scheduler.create_jobs(
                executable_steps, lambda step: job_calls[step.step_id]
            )
            self.state_store.save(state)

            batch_failed = len(jobs) != len(ready_steps)
            for outcome in self.scheduler.execute(jobs):
                step = steps_by_id[outcome.step_id]
                if outcome.error is not None:
                    state.fail_step(step.step_id, outcome.error)
                    step.status = StepStatus.FAILED
                    batch_failed = True
                else:
                    state.complete_step(step.step_id, outcome.output)
                    step.status = StepStatus.COMPLETED
            self.state_store.save(state)

            if batch_failed:
                self._block_pending_steps(
                    plan,
                    state,
                    "Blocked by a failed prerequisite step",
                )
                break

        if all(step.status == StepStatus.COMPLETED for step in plan.steps):
            state.complete()
            self.state_store.save(state)

        return self._assemble_result(plan, state)

    def get_execution(self, execution_id):
        return self.state_store.get(execution_id)

    def _build_context(self, plan, step, state, user_id, role, agent):
        return AgentContext(
            task=self._step_task(plan, step, state),
            user_id=user_id,
            role=role,
            agent_name=agent.agent_id,
            task_id=plan.task_id,
            step_id=step.step_id,
            capability=step.capability,
            goal=plan.goal,
            memory_context=self.aggregator.dependency_context(step, plan, state),
            available_tools=(
                getattr(agent.instance, "definition", None).allowed_tools
                if getattr(agent.instance, "definition", None)
                else []
            ),
            agent_definition=agent.definition or getattr(
                agent.instance, "definition", None
            ),
        )

    def _resolve_agent(self, capability):
        try:
            return self.registry.resolve_by_capability(capability)
        except KeyError as error:
            raise AgentResolutionError(
                f"No active Agent provides capability: {capability}"
            ) from error

    @staticmethod
    def _pending_steps(plan):
        return [step for step in plan.steps if step.status == StepStatus.PENDING]

    @staticmethod
    def _ready_steps(plan):
        statuses = {step.step_id: step.status for step in plan.steps}
        return [
            step
            for step in plan.steps
            if step.status == StepStatus.PENDING
            and all(
                statuses[dependency] == StepStatus.COMPLETED
                for dependency in step.dependencies
            )
        ]

    def _block_pending_steps(self, plan, state, reason):
        for step in self._pending_steps(plan):
            state.block_step(step.step_id, reason)
            step.status = StepStatus.BLOCKED
        self.state_store.save(state)

    def _step_task(self, plan, step, state):
        completed_results = self.aggregator.dependency_context(step, plan, state)
        return (
            f"Goal: {plan.goal}\n"
            f"Capability task: {step.capability}\n"
            f"Task context: {plan.context}\n"
            f"Previous results: {completed_results}\n"
            f"Step context: {step.context}"
        )

    def _assemble_result(self, plan, state):
        plan_steps = {step.step_id: step for step in plan.steps}
        steps = [
            StepResult(
                step_id=item.step_id,
                capability=plan_steps[item.step_id].capability,
                status=item.status,
                agent_id=item.agent_id,
                agent_version=item.agent_version,
                output=item.result,
                result_ref=item.result_ref,
                error=item.error,
            )
            for item in state.steps
        ]
        execution_context = self.aggregator.execution_context(plan, state)
        return SupervisionResult(
            execution_id=state.execution_id,
            task_id=state.task_id,
            status=state.status,
            output=(
                self.aggregator.final_output(plan, state)
                if execution_context
                else None
            ),
            steps=steps,
            replan_required=state.status
            in {ExecutionStatus.FAILED, ExecutionStatus.BLOCKED},
            execution_context=execution_context,
        )
