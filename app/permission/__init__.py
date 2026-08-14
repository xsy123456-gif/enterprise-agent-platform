"""Enterprise Permission Foundation.

A black-box authorization-decision service: given Subject + Resource + Action +
Environment + declarative Policy, it deterministically outputs ALLOW / DENY.
It knows nothing about Identity, Agent, Tool, Knowledge, Memory, Governance.
"""

from app.permission.api.service import PermissionService
from app.permission.config import PermissionConfig
from app.permission.evaluation.native import NativePolicyEvaluator
from app.permission.factory import PermissionSystem, build_permission
from app.permission.models import (
    AllCondition,
    AnyCondition,
    AtomicCondition,
    ConditionNode,
    Decision,
    NotCondition,
    PermissionDecision,
    PermissionEnvironment,
    PermissionPolicy,
    PermissionRequest,
    PermissionResource,
    PermissionScope,
    PermissionSubject,
    PolicyReference,
    PolicyScope,
    PolicySnapshot,
    PolicyTarget,
    ReasonCode,
    ResourceMatch,
    ScopeGrant,
)
from app.permission.ports.evaluator import PolicyEvaluatorPort
from app.permission.ports.policy_provider import PolicyProviderPort

__all__ = [
    "PermissionService",
    "PermissionConfig",
    "PermissionSystem",
    "build_permission",
    "NativePolicyEvaluator",
    "PermissionSubject",
    "PermissionScope",
    "ScopeGrant",
    "PermissionResource",
    "PermissionEnvironment",
    "PermissionRequest",
    "PermissionDecision",
    "Decision",
    "ReasonCode",
    "PolicyReference",
    "PermissionPolicy",
    "PolicyScope",
    "PolicyTarget",
    "ResourceMatch",
    "PolicySnapshot",
    "AtomicCondition",
    "AllCondition",
    "AnyCondition",
    "NotCondition",
    "ConditionNode",
    "PolicyProviderPort",
    "PolicyEvaluatorPort",
]
