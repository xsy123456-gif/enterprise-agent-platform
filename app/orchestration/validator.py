import json

from app.orchestration.plan import TaskPlan
from app.orchestration.task import TaskStep


class PlanValidationError(ValueError):
    pass


class PlanValidator:
    """Validates untrusted LLM plans before they enter deterministic control."""

    FORBIDDEN_FIELDS = {
        "agent",
        "agent_id",
        "permission",
        "runtime",
        "tool",
        "tool_name",
    }
    ALLOWED_PLAN_FIELDS = {"goal", "steps"}
    ALLOWED_STEP_FIELDS = {"step_id", "capability", "dependencies"}

    def __init__(self, catalog=None, registry=None):
        # ``registry`` is retained as a compatibility alias for v0.4 callers;
        # new orchestration paths must provide the CapabilityCatalog.
        self.catalog = catalog or registry
        if self.catalog is None:
            raise ValueError("PlanValidator requires a CapabilityCatalog")

    def validate(self, task, raw_plan):
        if not isinstance(raw_plan, dict):
            raise PlanValidationError("Plan must be a JSON object")

        self._reject_forbidden_fields(raw_plan)
        unknown = set(raw_plan) - self.ALLOWED_PLAN_FIELDS
        if unknown:
            raise PlanValidationError(
                f"Unknown plan fields: {sorted(unknown)}"
            )

        goal = raw_plan.get("goal")
        raw_steps = raw_plan.get("steps")
        if not isinstance(goal, str) or not goal.strip():
            raise PlanValidationError("Plan goal must be a non-empty string")
        if not isinstance(raw_steps, list) or not raw_steps:
            raise PlanValidationError("Plan steps must be a non-empty list")

        steps = []
        for raw_step in raw_steps:
            steps.append(self._validate_step(raw_step))

        try:
            return TaskPlan(
                task_id=task.task_id,
                goal=goal.strip(),
                steps=steps,
                context=dict(task.context),
            )
        except (TypeError, ValueError) as error:
            raise PlanValidationError(str(error)) from error

    def parse_and_validate(self, task, response):
        if isinstance(response, str):
            try:
                raw_plan = json.loads(response)
            except json.JSONDecodeError as error:
                raise PlanValidationError("LLM output is not valid JSON") from error
        else:
            raw_plan = response
        return self.validate(task, raw_plan)

    def _validate_step(self, raw_step):
        if not isinstance(raw_step, dict):
            raise PlanValidationError("Each plan step must be an object")
        self._reject_forbidden_fields(raw_step)
        unknown = set(raw_step) - self.ALLOWED_STEP_FIELDS
        if unknown:
            raise PlanValidationError(
                f"Unknown step fields: {sorted(unknown)}"
            )

        step_id = raw_step.get("step_id")
        capability = raw_step.get("capability")
        dependencies = raw_step.get("dependencies", [])
        if not isinstance(step_id, str) or not step_id.strip():
            raise PlanValidationError("step_id must be a non-empty string")
        if not isinstance(capability, str) or not capability.strip():
            raise PlanValidationError("capability must be a non-empty string")
        if not isinstance(dependencies, list) or not all(
            isinstance(item, str) and item.strip() for item in dependencies
        ):
            raise PlanValidationError("dependencies must be a list of step IDs")

        try:
            if hasattr(self.catalog, "get_capability"):
                self.catalog.get_capability(capability.strip())
            else:
                self.catalog.get(capability.strip())
        except KeyError as error:
            raise PlanValidationError(
                f"Unknown capability: {capability.strip()}"
            ) from error

        return TaskStep(
            step_id=step_id.strip(),
            capability=capability.strip(),
            dependencies=[item.strip() for item in dependencies],
        )

    def _reject_forbidden_fields(self, payload):
        forbidden = set(payload).intersection(self.FORBIDDEN_FIELDS)
        if forbidden:
            raise PlanValidationError(
                f"Forbidden plan fields: {sorted(forbidden)}"
            )
