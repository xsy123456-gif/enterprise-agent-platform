"""Phase 16.4 Workflow Engine tests."""

import pytest

from app.platform.business.errors import WorkflowError
from app.platform.business.workflow import (
    BusinessWorkflow,
    WorkflowEngine,
    WorkflowStep,
)


def _replenishment_workflow():
    return BusinessWorkflow(
        workflow_id="inventory_replenishment", version="1.0",
        steps=[
            WorkflowStep(step_id="s1", step_type="AGENT_TASK", name="诊断库存"),
            WorkflowStep(step_id="s2", step_type="APPROVAL", name="审批",
                         next_steps=("s3",)),
            WorkflowStep(step_id="s3", step_type="ACTION", name="创建采购订单",
                         next_steps=("s4",)),
            WorkflowStep(step_id="s4", step_type="NOTIFICATION", name="通知供应链"),
        ],
    )


def _handlers():
    return {
        "AGENT_TASK": lambda step, ctx: {"summary": "库存不足"},
        "APPROVAL": lambda step, ctx: {"approved": True},
        "ACTION": lambda step, ctx: {"done": True},
        "NOTIFICATION": lambda step, ctx: {"notified": True},
    }


def test_workflow_executes_in_order():
    engine = WorkflowEngine(_handlers())
    result = engine.run(_replenishment_workflow())
    assert result.status == "COMPLETED"
    assert set(result.step_results) == {"s1", "s2", "s3", "s4"}
    assert result.step_results["s1"] == {"summary": "库存不足"}


def test_workflow_cycle_rejected():
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[
            WorkflowStep(step_id="a", step_type="ACTION", next_steps=("b",)),
            WorkflowStep(step_id="b", step_type="ACTION", next_steps=("a",)),
        ],
    )
    with pytest.raises(WorkflowError):
        WorkflowEngine(_handlers()).run(workflow)


def test_workflow_step_failure_fails_workflow():
    def failing(step, ctx):
        raise RuntimeError("boom")

    handlers = _handlers()
    handlers["ACTION"] = failing
    engine = WorkflowEngine(handlers)
    result = engine.run(_replenishment_workflow())
    assert result.status == "FAILED"
    assert "s3" not in result.step_results


def test_workflow_missing_handler():
    workflow = BusinessWorkflow(
        workflow_id="w", version="1.0",
        steps=[WorkflowStep(step_id="a", step_type="WAIT")])
    with pytest.raises(WorkflowError):
        WorkflowEngine({}).run(workflow)
