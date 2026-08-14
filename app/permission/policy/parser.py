"""Policy parser — yaml dict -> PermissionPolicy objects."""

from app.permission.errors import PermissionPolicyError
from app.permission.models.condition import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    ConditionNode,
    NotCondition,
)
from app.permission.models.policy import (
    PermissionPolicy,
    PolicyScope,
    PolicyTarget,
    ResourceMatch,
)


def parse_condition(data) -> ConditionNode:
    if not isinstance(data, dict):
        raise PermissionPolicyError("condition must be an object")
    if "all" in data:
        conditions = data["all"]
        if not isinstance(conditions, list) or not conditions:
            raise PermissionPolicyError("'all' requires a non-empty list")
        return AllCondition(tuple(parse_condition(c) for c in conditions))
    if "any" in data:
        conditions = data["any"]
        if not isinstance(conditions, list) or not conditions:
            raise PermissionPolicyError("'any' requires a non-empty list")
        return AnyCondition(tuple(parse_condition(c) for c in conditions))
    if "not" in data:
        return NotCondition(parse_condition(data["not"]))
    field = data.get("field")
    operator = data.get("operator")
    if not field or not operator:
        raise PermissionPolicyError("atomic condition requires field and operator")
    if "value" in data and "value_from" in data:
        raise PermissionPolicyError("condition cannot have both value and value_from")
    return AtomicCondition(
        field=field,
        operator=operator,
        value=data.get("value"),
        value_from=data.get("value_from"),
        dimension=data.get("dimension"),
    )


def parse_policy(data: dict) -> PermissionPolicy:
    policy_id = data.get("policy_id")
    version = data.get("version")
    if not policy_id or not isinstance(version, int) or version <= 0:
        raise PermissionPolicyError(f"invalid policy identity: {policy_id!r} v{version!r}")

    scope_data = data.get("scope") or {}
    scope = PolicyScope(
        type=scope_data.get("type", "platform"),
        tenant_id=scope_data.get("tenant_id"),
    )

    target_data = data.get("target") or {}
    match_data = target_data.get("resource_match") or {}
    target = PolicyTarget(
        resource_types=frozenset(target_data.get("resource_types") or ()),
        resource_match=ResourceMatch(
            type=match_data.get("type", "any"),
            ids=frozenset(match_data.get("ids") or ()),
        ),
        actions=frozenset(target_data.get("actions") or ()),
    )

    condition = parse_condition(data["condition"]) if data.get("condition") else None

    return PermissionPolicy(
        policy_id=policy_id,
        version=version,
        status=data.get("status", "active"),
        scope=scope,
        effect=data.get("effect", "allow"),
        target=target,
        condition=condition,
    )


def parse_policies(payload: dict) -> list[PermissionPolicy]:
    items = payload.get("policies") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise PermissionPolicyError("policy document requires a 'policies' list")
    return [parse_policy(item) for item in items]
