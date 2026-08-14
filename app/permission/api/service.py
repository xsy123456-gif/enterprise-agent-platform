"""PermissionService — the single authorization entrypoint."""

import uuid

from app.permission.config import PermissionConfig
from app.permission.evaluation.native import NativePolicyEvaluator
from app.permission.errors import PermissionUnavailableError, PermissionValidationError
from app.permission.models.decision import (
    Decision,
    PermissionDecision,
    ReasonCode,
)
from app.permission.models.request import PermissionRequest
from app.permission.ports.evaluator import PolicyEvaluatorPort
from app.permission.runtime import PermissionRuntime
from app.permission.validation.request_validator import validate_request


class PermissionService:
    def __init__(
        self,
        runtime: PermissionRuntime,
        evaluator: PolicyEvaluatorPort | None = None,
        config: PermissionConfig | None = None,
    ):
        if runtime is None:
            raise ValueError("PermissionService requires a PermissionRuntime")
        self.runtime = runtime
        self.evaluator = evaluator or NativePolicyEvaluator()
        self.config = config or PermissionConfig()

    def evaluate(self, request: PermissionRequest) -> PermissionDecision:
        decision_id = str(uuid.uuid4())

        try:
            validate_request(request)
        except PermissionValidationError:
            return self._deny(request, decision_id, ReasonCode.DENY_INVALID_REQUEST)

        try:
            snapshot = self.runtime.get_snapshot()
        except PermissionUnavailableError:
            return self._deny(request, decision_id, ReasonCode.DENY_POLICY_UNAVAILABLE)

        try:
            result = self.evaluator.evaluate(request, snapshot)
        except Exception:
            return self._deny(request, decision_id, ReasonCode.DENY_EVALUATION_ERROR)

        return PermissionDecision(
            decision=result.decision,
            decision_id=decision_id,
            request_id=request.request_id,
            reason_code=result.reason_code,
            matched_policy_refs=result.matched_policy_refs,
            policy_set_version=result.policy_set_version,
        )

    @staticmethod
    def _deny(request, decision_id, reason_code) -> PermissionDecision:
        return PermissionDecision(
            decision=Decision.DENY,
            decision_id=decision_id,
            request_id=request.request_id,
            reason_code=reason_code,
        )
