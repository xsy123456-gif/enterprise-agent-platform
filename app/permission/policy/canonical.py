"""Deterministic canonicalization + policy_set_version.

The policy set version is a SHA-256 over the canonical serialization of all
policies (sorted, order-independent).  YAML key order or file order must never
change it.
"""

import hashlib
import json

from app.permission.models.condition import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    NotCondition,
)
from app.permission.models.policy import PermissionPolicy


def _sort_value(value):
    if isinstance(value, (list, tuple, set, frozenset)):
        return sorted(_sort_value(item) for item in value)
    if isinstance(value, dict):
        return {key: _sort_value(item) for key, item in sorted(value.items())}
    return value


def _condition_to_canonical(node):
    if isinstance(node, AtomicCondition):
        return {
            "field": node.field,
            "operator": node.operator,
            "value": _sort_value(node.value),
            "value_from": node.value_from,
            "dimension": node.dimension,
        }
    if isinstance(node, AllCondition):
        return {"all": [_condition_to_canonical(c) for c in node.conditions]}
    if isinstance(node, AnyCondition):
        return {"any": [_condition_to_canonical(c) for c in node.conditions]}
    if isinstance(node, NotCondition):
        return {"not": _condition_to_canonical(node.condition)}
    raise TypeError(f"unknown condition node: {type(node).__name__}")


def policy_to_canonical(policy: PermissionPolicy) -> dict:
    return {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "status": policy.status,
        "scope": {
            "type": policy.scope.type,
            "tenant_id": policy.scope.tenant_id,
        },
        "effect": policy.effect,
        "target": {
            "resource_types": sorted(policy.target.resource_types),
            "resource_match": {
                "type": policy.target.resource_match.type,
                "ids": sorted(policy.target.resource_match.ids),
            },
            "actions": sorted(policy.target.actions),
        },
        "condition": (
            _condition_to_canonical(policy.condition)
            if policy.condition is not None
            else None
        ),
    }


def compute_policy_set_version(policies) -> str:
    canonical = [policy_to_canonical(p) for p in policies]
    serialized = json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
