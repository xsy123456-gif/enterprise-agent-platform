"""Agent governance (Phase 13.4).

Enterprise access control: who may use which agent.  Agents only declare
``required_department`` (via manifest); they never store a user list / role /
department.  Access is decided here (fail-closed: no matching policy -> deny).
"""

from dataclasses import dataclass

from app.platform.agent_control.domain import (
    AGENT_PERMISSIONS,
    SUBJECT_DEPARTMENT,
    SUBJECT_ROLE,
    SUBJECT_TYPES,
    SUBJECT_USER,
)
from app.platform.agent_control.errors import AgentAccessDeniedError


@dataclass(frozen=True)
class AgentAccessPolicy:
    policy_id: str
    agent_id: str
    subject_type: str
    subject_id: str
    permission: str

    def __post_init__(self):
        if not self.agent_id:
            raise ValueError("agent_id is required")
        if self.subject_type not in SUBJECT_TYPES:
            raise ValueError(f"unknown subject_type: {self.subject_type}")
        if self.permission not in AGENT_PERMISSIONS:
            raise ValueError(f"unknown permission: {self.permission}")

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "agent_id": self.agent_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "permission": self.permission,
        }


class AgentAccessControl:

    def __init__(self, policies=None):
        self._policies = list(policies or [])

    def add_policy(self, policy: AgentAccessPolicy):
        self._policies.append(policy)
        return policy

    def policies_for(self, agent_id):
        return [p for p in self._policies if p.agent_id == agent_id]

    def check(self, agent_id, subject, permission) -> bool:
        """Return True if ``subject`` has ``permission`` on ``agent_id``.

        ``subject`` is duck-typed with ``subject_id``, ``roles`` (iterable) and
        ``department_id``.  Fail-closed: any mismatch denies.
        """
        for policy in self._policies:
            if policy.agent_id != agent_id or policy.permission != permission:
                continue
            if policy.subject_type == SUBJECT_USER and \
                    policy.subject_id == getattr(subject, "subject_id", None):
                return True
            if policy.subject_type == SUBJECT_ROLE and \
                    policy.subject_id in (getattr(subject, "roles", None) or ()):
                return True
            if policy.subject_type == SUBJECT_DEPARTMENT and \
                    policy.subject_id == getattr(subject, "department_id", None):
                return True
        return False

    def authorize(self, agent_id, subject, permission):
        if not self.check(agent_id, subject, permission):
            raise AgentAccessDeniedError(
                f"subject {getattr(subject, 'subject_id', '?')!r} lacks "
                f"{permission!r} on agent {agent_id!r}"
            )


__all__ = ["AgentAccessPolicy", "AgentAccessControl"]
