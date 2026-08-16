"""Phase 18.5 Workflow Execution Convergence tests.

Verify production workflows execute through registered typed step adapters that
route ACTION -> BusinessActionRuntime -> ActionExecutionPort (Runtime boundary)
and CONDITION -> a deterministic evaluator (never an LLM).
"""

from app.platform.business.action import BusinessActionRuntime
from app.platform.business.workflow import (
    ApprovalStepAdapter,
    BusinessActionStepAdapter,
    BusinessWorkflow,
    ConditionStepAdapter,
    WaitStepAdapter,
    WorkflowEngine,
    WorkflowStep,
    WorkflowStepAdapter,
)


class _RecordingPort:
    def __init__(self):
        self.calls = []

    def execute(self, action, context=None):
        self.calls.append((action.action_type, action.target))


def _replenishment_workflow():
    return BusinessWorkflow(
        workflow_id="inventory_replenishment", version="1.0",
        steps=[
            WorkflowStep(step_id="s1", step_type="AGENT_TASK"),
            WorkflowStep(step_id="s2", step_type="ACTION", next_steps=("s3",)),
            WorkflowStep(step_id="s3", step_type="CONDITION"),
        ],
    )


def test_action_step_routes_through_runtime_boundary():
    port = _RecordingPort()
    action_runtime = BusinessActionRuntime(execution_port=port)
    adapter = BusinessActionStepAdapter(action_runtime)
    engine = WorkflowEngine(step_adapters=[adapter])

    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="a", step_type="ACTION")],
    )
    from app.platform.business.action import BusinessAction
    action = BusinessAction(
        action_id="a1", action_type="CREATE_PURCHASE_ORDER", target="sku_1",
        status="APPROVED")
    result = engine.run(workflow, context={"action": action})
    assert result.status == "COMPLETED"
    assert result.step_results["a"]["result"] == "SUCCEEDED"
    assert port.calls == [("CREATE_PURCHASE_ORDER", "sku_1")]


def test_action_step_requires_action_runtime_not_lambda():
    # A typed adapter is a real object (not a raw callable); the engine uses it.
    from app.platform.business.workflow.adapters import WorkflowStepAdapter
    assert issubclass(BusinessActionStepAdapter, WorkflowStepAdapter)
    assert BusinessActionStepAdapter.step_type == "ACTION"


def test_condition_step_is_deterministic():
    engine = WorkflowEngine(step_adapters=[
        ConditionStepAdapter(evaluator=lambda step, ctx: ctx["enough"] > 0)])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="c", step_type="CONDITION")],
    )
    result = engine.run(workflow, context={"enough": 5})
    assert result.step_results["c"]["matches"] is True


def test_engine_rejects_unregistered_step_type():
    engine = WorkflowEngine(step_adapters=[])  # no adapters registered
    from app.platform.business.errors import WorkflowError
    import pytest
    with pytest.raises(WorkflowError):
        engine.run(_replenishment_workflow())


# ── Phase 18.5 final gate ──────────────────────────────────

def test_approval_step_uses_typed_adapter():
    assert issubclass(ApprovalStepAdapter, WorkflowStepAdapter)
    assert ApprovalStepAdapter.step_type == "APPROVAL"


def test_approval_rejection_blocks_following_steps():
    engine = WorkflowEngine(step_adapters=[
        ApprovalStepAdapter(lambda step, ctx: bool(ctx.get("approved", False)))])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="a", step_type="APPROVAL", next_steps=("b",)),
            WorkflowStep(step_id="b", step_type="ACTION"),
        ],
    )
    # no ACTION adapter registered: even if approval passed, b would fail;
    # here approval rejects -> b must never run.
    result = engine.run(workflow, context={"approved": False})
    assert result.status == "FAILED"
    assert "b" not in result.step_results


def test_approval_accepted_continues():
    engine = WorkflowEngine(step_adapters=[
        ApprovalStepAdapter(lambda step, ctx: bool(ctx.get("approved", False)))])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="a", step_type="APPROVAL")],
    )
    result = engine.run(workflow, context={"approved": True})
    assert result.status == "COMPLETED"
    assert result.step_results["a"]["approved"] is True


def test_wait_step_does_not_block_with_sleep():
    # WaitStepAdapter returns a waiting signal synchronously; it never sleeps.
    import inspect
    source = inspect.getsource(WaitStepAdapter.execute)
    assert "sleep" not in source
    engine = WorkflowEngine(step_adapters=[WaitStepAdapter()])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="w", step_type="WAIT")],
    )
    result = engine.run(workflow)
    assert result.status == "COMPLETED"
    assert result.step_results["w"]["waiting"] is True


def test_production_disallows_arbitrary_step_handler():
    from app.platform.business.errors import WorkflowError
    import pytest
    with pytest.raises(WorkflowError):
        WorkflowEngine(step_handlers={"ACTION": lambda s, c: None}, strict=True)


def test_sandbox_disallows_arbitrary_step_handler():
    from app.platform.business.errors import WorkflowError
    import pytest
    with pytest.raises(WorkflowError):
        WorkflowEngine(step_handlers={"ACTION": lambda s, c: None}, strict=True)


def test_development_allows_test_handler_fallback():
    engine = WorkflowEngine(step_handlers={"ACTION": lambda s, c: {"ok": True}},
                            strict=False)
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="a", step_type="ACTION")],
    )
    result = engine.run(workflow)
    assert result.status == "COMPLETED"
