"""Policy set validation — fail-closed, no silent skip."""

from app.permission.errors import PermissionPolicyError
from app.permission.models.condition import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    NotCondition,
)

VALID_OPERATORS = {
    "equals", "not_equals", "in", "not_in", "contains", "contains_any",
    "contains_all", "gt", "gte", "lt", "lte", "gte_level", "lte_level",
    "exists", "not_exists", "scope_contains",
}
VALID_EFFECTS = {"allow", "deny"}
VALID_STATUSES = {"active", "disabled"}
VALID_SCOPE_TYPES = {"platform", "tenant"}
VALID_MATCH_TYPES = {"any", "ids"}


def validate_policy_set(policies, config) -> None:
    active: dict[str, object] = {}
    for policy in policies:
        _validate_policy(policy, config)
        if policy.status == "active":
            if policy.policy_id in active:
                raise PermissionPolicyError(
                    f"duplicate active version for policy: {policy.policy_id}"
                )
            active[policy.policy_id] = policy


def _validate_policy(policy, config) -> None:
    if policy.effect not in VALID_EFFECTS:
        raise PermissionPolicyError(f"invalid effect: {policy.effect!r}")
    if policy.status not in VALID_STATUSES:
        raise PermissionPolicyError(f"invalid status: {policy.status!r}")
    if policy.scope.type not in VALID_SCOPE_TYPES:
        raise PermissionPolicyError(f"invalid scope type: {policy.scope.type!r}")
    if policy.scope.type == "tenant" and not policy.scope.tenant_id:
        raise PermissionPolicyError("tenant policy requires tenant_id")
    match_type = policy.target.resource_match.type
    if match_type not in VALID_MATCH_TYPES:
        raise PermissionPolicyError(f"invalid resource_match type: {match_type!r}")
    if match_type == "ids" and not policy.target.resource_match.ids:
        raise PermissionPolicyError("resource_match ids requires a non-empty set")

    depth, nodes = _validate_condition(policy.condition)
    if depth > config.max_condition_depth:
        raise PermissionPolicyError(
            f"condition depth {depth} exceeds {config.max_condition_depth}"
        )
    if nodes > config.max_condition_nodes:
        raise PermissionPolicyError(
            f"condition nodes {nodes} exceeds {config.max_condition_nodes}"
        )


def _validate_condition(node):
    if node is None:
        return 0, 0
    if isinstance(node, AtomicCondition):
        if node.operator not in VALID_OPERATORS:
            raise PermissionPolicyError(f"unknown operator: {node.operator!r}")
        if node.operator == "scope_contains" and not node.dimension:
            raise PermissionPolicyError("scope_contains requires a dimension")
        has_value = node.value is not None
        has_value_from = node.value_from is not None
        if has_value and has_value_from:
            raise PermissionPolicyError("condition has both value and value_from")
        if node.operator not in {"exists", "not_exists"} and not (has_value or has_value_from):
            raise PermissionPolicyError(
                f"operator {node.operator} requires value or value_from"
            )
        return 1, 1
    if isinstance(node, (AllCondition, AnyCondition)):
        if not node.conditions:
            raise PermissionPolicyError("all/any requires a non-empty list")
        total_depth, total_nodes = 1, 1
        for child in node.conditions:
            child_depth, child_nodes = _validate_condition(child)
            total_depth = max(total_depth, child_depth + 1)
            total_nodes += child_nodes
        return total_depth, total_nodes
    if isinstance(node, NotCondition):
        if node.condition is None:
            raise PermissionPolicyError("not requires a condition")
        depth, nodes = _validate_condition(node.condition)
        return depth + 1, nodes + 1
    raise PermissionPolicyError(f"unknown condition node: {type(node).__name__}")
