"""Business action runtime (Phase 16.3 + 18.3).

Governance runtime: validate -> permission -> approval -> (idempotency +
precondition) -> dispatch -> audit.  The *actual* external execution goes
through ``ActionExecutionPort`` (fulfilled by the Runtime Foundation), never
through a private ``action_handler`` in production.  ``action_handler`` remains
only as a test/development convenience.
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
from app.platform.business.action.repository import (
    BusinessActionRepository,
    InMemoryBusinessActionRepository,
)
from app.platform.business.action.runtime import ActionExecutor
from app.platform.business.errors import (
    ActionExecutionError,
    ApprovalRequiredError,
)


class BusinessActionRuntime(ActionExecutor):

    def __init__(self, approval_engine=None, permission_checker=None,
                 action_handler=None, audit=None, execution_port=None,
                 idempotency_store=None, precondition_checker=None,
                 repository=None):
        self.approval_engine = approval_engine
        self.permission_checker = permission_checker
        self.action_handler = action_handler
        self.audit = audit
        self.execution_port = execution_port
        self.idempotency_store = idempotency_store
        self.precondition_checker = precondition_checker
        self.repository = repository or InMemoryBusinessActionRepository()

    def create_action(self, proposal) -> BusinessAction:
        action = BusinessAction(
            action_id=uuid.uuid4().hex, action_type=proposal.action_type,
            target=proposal.target, parameters=proposal.parameters,
            risk_level=proposal.risk_level, created_by=proposal.agent_id,
        )
        if self._needs_approval(action):
            action = replace(action, status=ACTION_WAITING_APPROVAL)
        else:
            action = replace(action, status=ACTION_APPROVED)
        self.repository.put(action)
        return action

    def approve(self, action, approver):
        updated = replace(action, status=ACTION_APPROVED,
                          parameters={**action.parameters, "approved_by": approver})
        self.repository.put(updated)
        return updated

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
        existing = self._idempotent_result(action)
        if existing is not None:
            return existing
        self._check_precondition(action, context)
        running = replace(action, status=ACTION_EXECUTING)
        self.repository.put(running)
        try:
            self._dispatch(running, context)
            result = replace(running, status=ACTION_SUCCEEDED)
        except Exception as error:  # noqa: BLE001 - recorded in audit
            result = replace(running, status=ACTION_FAILED)
            self.repository.put(result)
            if self.audit is not None:
                self.audit.record(action.action_id, "Failed", str(error))
            raise ActionExecutionError(str(error))
        self._record_idempotency(action, result)
        self.repository.put(result)
        if self.audit is not None:
            self.audit.record(action.action_id, "Executed", "")
        return result

    def _dispatch(self, action, context):
        if self.execution_port is not None:
            self.execution_port.execute(action, context)
        elif self.action_handler is not None:
            self.action_handler(action, context)
        else:
            raise ActionExecutionError("no execution port configured")

    def _idempotent_result(self, action):
        if self.idempotency_store is None or not action.idempotency_key:
            return None
        return self.idempotency_store.get(action.idempotency_key)

    def _record_idempotency(self, action, result):
        if self.idempotency_store is not None and action.idempotency_key:
            self.idempotency_store.put(action.idempotency_key, result)

    def _check_precondition(self, action, context):
        if self.precondition_checker is None or not action.expected_resource_version:
            return
        ok, detail = self.precondition_checker(action, context)
        if not ok:
            raise ActionExecutionError(
                f"precondition failed for {action.target!r}: {detail}"
            )

    def _needs_approval(self, action):
        if self.approval_engine is None:
            return False
        return self.approval_engine.requires_approval(action.action_type,
                                                      action.risk_level)


class InMemoryIdempotencyStore:

    def __init__(self):
        self._results = {}

    def get(self, key):
        return self._results.get(key)

    def put(self, key, result):
        self._results[key] = result


__all__ = ["BusinessActionRuntime", "InMemoryIdempotencyStore"]
