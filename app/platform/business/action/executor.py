"""Business action runtime (Phase 16.3).

The concrete ``ActionExecutor``: validate -> permission -> approval -> execute
-> audit.  Fail-closed on every gate; a denied/unauthorized action never
reaches the handler.
"""

import uuid
from dataclasses import replace

from app.platform.business.action.domain import (
    ACTION_APPROVED,
    ACTION_EXECUTING,
    ACTION_FAILED,
    ACTION_SUCCEEDED,
    ACTION_WAITING_APPROVAL,
    BusinessAction,
)
from app.platform.business.action.runtime import ActionExecutor
from app.platform.business.errors import (
    ActionExecutionError,
    ApprovalRequiredError,
)


class BusinessActionRuntime(ActionExecutor):

    def __init__(self, approval_engine=None, permission_checker=None,
                 action_handler=None, audit=None):
        self.approval_engine = approval_engine
        self.permission_checker = permission_checker
        self.action_handler = action_handler
        self.audit = audit

    def create_action(self, proposal) -> BusinessAction:
        action = BusinessAction(
            action_id=uuid.uuid4().hex, action_type=proposal.action_type,
            target=proposal.target, parameters=proposal.parameters,
            risk_level=proposal.risk_level, created_by=proposal.agent_id,
        )
        if self._needs_approval(action):
            return replace(action, status=ACTION_WAITING_APPROVAL)
        return replace(action, status=ACTION_APPROVED)

    def approve(self, action, approver):
        return replace(action, status=ACTION_APPROVED,
                       parameters={**action.parameters, "approved_by": approver})

    def execute(self, action, context=None):
        if not action.action_type or not action.target:
            raise ActionExecutionError("action requires action_type and target")
        if self.permission_checker is not None:
            if not self.permission_checker(action):
                raise ActionExecutionError(
                    f"permission denied for action {action.action_type!r}"
                )
        if self._needs_approval(action) and action.status != ACTION_APPROVED:
            raise ApprovalRequiredError(
                f"action {action.action_id!r} requires approval"
            )
        running = replace(action, status=ACTION_EXECUTING)
        try:
            if self.action_handler is not None:
                self.action_handler(running, context)
            result = replace(running, status=ACTION_SUCCEEDED)
        except Exception as error:  # noqa: BLE001 - recorded in audit
            result = replace(running, status=ACTION_FAILED)
            if self.audit is not None:
                self.audit.record(action.action_id, "Failed", str(error))
            raise ActionExecutionError(str(error))
        if self.audit is not None:
            self.audit.record(action.action_id, "Executed", "")
        return result

    def _needs_approval(self, action):
        if self.approval_engine is None:
            return False
        return self.approval_engine.requires_approval(action.action_type,
                                                      action.risk_level)


__all__ = ["BusinessActionRuntime"]
