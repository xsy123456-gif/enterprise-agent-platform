from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class ApprovalRecord:
    approval_id: str
    execution_id: str
    status: str = "pending"
    context: dict = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ApprovalAdapter:
    """Execution approval port; approval policy remains outside LangGraph."""

    def __init__(self, workflow=None):
        self.workflow = workflow
        self.records: dict[str, ApprovalRecord] = {}

    def request_approval(self, context):
        if self.workflow is not None and hasattr(self.workflow, "request_approval"):
            return self.workflow.request_approval(context)
        approval = ApprovalRecord(
            approval_id=str(uuid.uuid4()),
            execution_id=context.execution_id,
            context={
                "agent_id": context.agent_id,
                "tool_name": context.tool_name,
                "risk_level": context.risk_level,
            },
        )
        self.records[approval.approval_id] = approval
        return approval

    def complete(self, approval_id, approved, reviewer=None):
        if self.workflow is not None and hasattr(self.workflow, "complete"):
            return self.workflow.complete(approval_id, approved, reviewer)
        record = self.records[approval_id]
        record.status = "approved" if approved else "rejected"
        record.context["reviewer"] = reviewer
        return record
