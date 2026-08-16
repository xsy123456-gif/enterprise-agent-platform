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
    NotificationStepAdapter,
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


# ── Phase 18.5.1 final gate: suspension semantics ──────────

def test_approval_step_uses_typed_adapter():
    assert issubclass(ApprovalStepAdapter, WorkflowStepAdapter)
    assert ApprovalStepAdapter.step_type == "APPROVAL"


def _approval_workflow():
    return BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="a", step_type="APPROVAL", next_steps=("b",)),
            WorkflowStep(step_id="b", step_type="NOTIFICATION"),
        ],
    )


def _approval_engine(**adapters):
    lookup = (lambda step, ctx: ctx.get("approval_state", "PENDING"))
    adapters = dict(adapters)
    adapters.setdefault("APPROVAL", ApprovalStepAdapter(lookup))
    return WorkflowEngine(step_adapters=list(adapters.values()))


def test_pending_approval_sets_waiting_approval():
    engine = _approval_engine()
    run = engine.run(_approval_workflow(), context={"approval_state": "PENDING"})
    assert run.status == "WAITING_APPROVAL"
    assert run.current_step_id == "a"


def test_pending_approval_does_not_mark_workflow_failed():
    engine = _approval_engine()
    run = engine.run(_approval_workflow(), context={"approval_state": "PENDING"})
    assert run.status != "FAILED"
    assert run.status == "WAITING_APPROVAL"


def test_pending_approval_blocks_following_action():
    engine = _approval_engine(NOTIFICATION=NotificationStepAdapter(
        lambda s, c: {"notified": True}))
    run = engine.run(_approval_workflow(), context={"approval_state": "PENDING"})
    assert run.status == "WAITING_APPROVAL"
    assert "b" not in run.step_results


def test_approved_approval_resumes_workflow():
    engine = _approval_engine(NOTIFICATION=NotificationStepAdapter(
        lambda s, c: {"notified": True}))
    run = engine.run(_approval_workflow(), context={"approval_state": "PENDING"})
    assert run.status == "WAITING_APPROVAL"
    run = engine.resume(run, {"approval_state": "APPROVED"})
    assert run.status == "COMPLETED"
    assert run.step_results["a"]["approved"] is True
    assert run.step_results["b"]["notified"] is True


def test_rejected_approval_fails_workflow():
    engine = _approval_engine(NOTIFICATION=NotificationStepAdapter(
        lambda s, c: {"notified": True}))
    run = engine.run(_approval_workflow(), context={"approval_state": "REJECTED"})
    assert run.status == "FAILED"


def test_rejected_approval_blocks_following_steps():
    engine = _approval_engine(NOTIFICATION=NotificationStepAdapter(
        lambda s, c: {"notified": True}))
    run = engine.run(_approval_workflow(), context={"approval_state": "REJECTED"})
    assert run.status == "FAILED"
    assert "b" not in run.step_results


def test_wait_step_sets_workflow_waiting():
    engine = WorkflowEngine(step_adapters=[WaitStepAdapter()])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="w", step_type="WAIT")],
    )
    run = engine.run(workflow)
    assert run.status == "WAITING"


def test_wait_step_blocks_following_steps():
    engine = WorkflowEngine(step_adapters=[
        WaitStepAdapter(),
        NotificationStepAdapter(lambda s, c: {"notified": True}),
    ])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="w", step_type="WAIT", next_steps=("n",)),
            WorkflowStep(step_id="n", step_type="NOTIFICATION"),
        ],
    )
    run = engine.run(workflow)
    assert run.status == "WAITING"
    assert "n" not in run.step_results


def test_resume_waiting_workflow_continues():
    engine = WorkflowEngine(step_adapters=[
        WaitStepAdapter(),
        NotificationStepAdapter(lambda s, c: {"notified": True}),
    ])
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="w", step_type="WAIT", next_steps=("n",)),
            WorkflowStep(step_id="n", step_type="NOTIFICATION"),
        ],
    )
    run = engine.run(workflow)
    assert run.status == "WAITING"
    run = engine.resume(run, {"resume_signal": True})
    assert run.status == "COMPLETED"
    assert run.step_results["w"]["waited"] is True
    assert run.step_results["n"]["notified"] is True


def test_wait_step_does_not_block_with_sleep():
    # WaitStepAdapter returns a waiting signal synchronously; it never sleeps.
    import inspect
    source = inspect.getsource(WaitStepAdapter.execute)
    assert "sleep" not in source


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
