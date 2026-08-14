"""Permission decision — the authorization outcome."""

from dataclasses import dataclass, field
from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class ReasonCode(str, Enum):
    ALLOWED_POLICY_MATCH = "ALLOWED_POLICY_MATCH"
    DENY_NO_MATCH = "DENY_NO_MATCH"
    DENY_EXPLICIT = "DENY_EXPLICIT"
    DENY_TENANT_MISMATCH = "DENY_TENANT_MISMATCH"
    DENY_INVALID_REQUEST = "DENY_INVALID_REQUEST"
    DENY_POLICYSET_INVALID = "DENY_POLICYSET_INVALID"
    DENY_POLICY_UNAVAILABLE = "DENY_POLICY_UNAVAILABLE"
    DENY_EVALUATION_ERROR = "DENY_EVALUATION_ERROR"
    DENY_INDETERMINATE = "DENY_INDETERMINATE"


@dataclass(frozen=True)
class PolicyReference:
    policy_id: str
    version: int

    def to_dict(self):
        return {"policy_id": self.policy_id, "version": self.version}


@dataclass(frozen=True)
class PermissionDecision:
    decision: Decision
    decision_id: str
    request_id: str
    reason_code: ReasonCode
    matched_policy_refs: tuple[PolicyReference, ...] = ()
    policy_set_version: str = ""

    def to_dict(self):
        return {
            "decision": self.decision.value,
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "reason_code": self.reason_code.value,
            "matched_policy_refs": [r.to_dict() for r in self.matched_policy_refs],
            "policy_set_version": self.policy_set_version,
        }

    @property
    def allowed(self):
        return self.decision is Decision.ALLOW
