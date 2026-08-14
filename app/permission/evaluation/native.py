"""Native policy evaluator — the deterministic reference implementation.

Pipeline (fixed order): tenant check -> scope filter -> target match ->
condition evaluation -> effect collection -> combination.
"""

from app.permission.evaluation.combiner import EvaluationResult, combine
from app.permission.evaluation.field_resolver import resolve_field
from app.permission.evaluation.operators import TruthValue, apply
from app.permission.models.condition import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    NotCondition,
)
from app.permission.models.decision import Decision, ReasonCode
from app.permission.models.request import PermissionRequest
from app.permission.models.snapshot import PolicySnapshot


class NativePolicyEvaluator:
    """Pure, side-effect-free evaluator: Request + Snapshot -> EvaluationResult."""

    def evaluate(self, request: PermissionRequest, snapshot: PolicySnapshot) -> EvaluationResult:
        if request.subject.tenant_id != request.resource.tenant_id:
            return EvaluationResult(
                Decision.DENY, ReasonCode.DENY_TENANT_MISMATCH,
                (), snapshot.policy_set_version,
            )

        matches = []
        for policy in snapshot.policies:
            if policy.status != "active":
                continue
            if not self._scope_applies(policy, request):
                continue
            if not self._target_matches(policy, request):
                continue
            truth = self._eval_condition(policy.condition, request)
            matches.append((policy, truth))

        return combine(matches, snapshot.policy_set_version)

    @staticmethod
    def _scope_applies(policy, request) -> bool:
        scope = policy.scope
        if scope.type == "platform":
            return True
        if scope.type == "tenant":
            return scope.tenant_id == request.subject.tenant_id
        return False

    @staticmethod
    def _target_matches(policy, request) -> bool:
        target = policy.target
        if target.resource_types and request.resource.resource_type not in target.resource_types:
            return False
        match = target.resource_match
        if match.type == "ids" and request.resource.resource_id not in match.ids:
            return False
        if target.actions and request.action not in target.actions:
            return False
        return True

    def _eval_condition(self, node, request) -> TruthValue:
        if node is None:
            return TruthValue.TRUE
        if isinstance(node, AtomicCondition):
            return self._eval_atomic(node, request)
        if isinstance(node, AllCondition):
            return self._eval_all(node.conditions, request)
        if isinstance(node, AnyCondition):
            return self._eval_any(node.conditions, request)
        if isinstance(node, NotCondition):
            return self._eval_not(self._eval_condition(node.condition, request))
        return TruthValue.ERROR

    @staticmethod
    def _eval_atomic(node, request) -> TruthValue:
        left = resolve_field(request, node.field)
        if node.value_from:
            right = resolve_field(request, node.value_from)
        else:
            right = node.value
        return apply(node.operator, left, right, node.dimension)

    def _eval_all(self, conditions, request) -> TruthValue:
        results = [self._eval_condition(c, request) for c in conditions]
        if any(r is TruthValue.ERROR for r in results):
            return TruthValue.ERROR
        if any(r is TruthValue.FALSE for r in results):
            return TruthValue.FALSE
        if any(r is TruthValue.UNKNOWN for r in results):
            return TruthValue.UNKNOWN
        return TruthValue.TRUE

    def _eval_any(self, conditions, request) -> TruthValue:
        results = [self._eval_condition(c, request) for c in conditions]
        if any(r is TruthValue.ERROR for r in results):
            return TruthValue.ERROR
        if any(r is TruthValue.TRUE for r in results):
            return TruthValue.TRUE
        if any(r is TruthValue.UNKNOWN for r in results):
            return TruthValue.UNKNOWN
        return TruthValue.FALSE

    @staticmethod
    def _eval_not(value) -> TruthValue:
        return {
            TruthValue.TRUE: TruthValue.FALSE,
            TruthValue.FALSE: TruthValue.TRUE,
            TruthValue.UNKNOWN: TruthValue.UNKNOWN,
            TruthValue.ERROR: TruthValue.ERROR,
        }[value]
