"""Approval + workflow public mappers (Phase 18.12)."""

from app.api.v1.schemas.approvals import ApprovalSummary, WorkflowRunResponse


def approval_summary_from(request) -> ApprovalSummary:
    return ApprovalSummary(
        approval_id=request.approval_id,
        status=request.status,
        risk_level=getattr(request, "risk_level", ""),
        action_type=getattr(request, "action_id", "") or "",
        summary=getattr(request, "summary", ""),
        created_at=getattr(request, "created_at", None),
    )


def workflow_run_response_from(run) -> WorkflowRunResponse:
    from app.api.v1.schemas.approvals import WorkflowStepStatus
    steps = []
    order = getattr(run, "order", []) or []
    for step_id in order:
        step = run.workflow.step(step_id)
        if step_id in run.step_results:
            status = "COMPLETED"
        elif step_id == run.current_step_id:
            status = "WAITING"
        else:
            status = "PENDING"
        steps.append(WorkflowStepStatus(
            step_id=step_id, type=step.step_type, status=status))
    waiting = None
    if run.status == "WAITING_APPROVAL":
        waiting = {"type": "APPROVAL", "step_id": run.current_step_id}
    elif run.status == "WAITING":
        waiting = {"type": "WAIT", "step_id": run.current_step_id}
    return WorkflowRunResponse(
        run_id=run.run_id,
        workflow_id=run.workflow.workflow_id,
        version=getattr(run.workflow, "version", ""),
        status=run.status,
        steps=steps,
        waiting=waiting,
    )


__all__ = ["approval_summary_from", "workflow_run_response_from"]
