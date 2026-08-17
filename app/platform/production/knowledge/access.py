"""Knowledge access governance (Phase 15.5).

Enterprise knowledge permission: a document is accessible only to agents it is
explicitly granted to (fail-closed default deny).
"""

from dataclasses import dataclass

from app.platform.production.errors import KnowledgeAccessDeniedError


@dataclass(frozen=True)
class KnowledgeAccessPolicy:
    policy_id: str
    document_id: str
    agent_id: str
    allowed: bool = True

    def __post_init__(self):
        if not self.document_id:
            raise ValueError("document_id is required")
        if not self.agent_id:
            raise ValueError("agent_id is required")


class KnowledgeAccessControl:

    def __init__(self, policies=None):
        self._policies = list(policies or [])

    def add_policy(self, policy):
        self._policies.append(policy)
        return policy

    def check(self, document_id, agent_id) -> bool:
        for policy in self._policies:
            if policy.document_id == document_id and policy.agent_id == agent_id:
                return policy.allowed
        return False

    def authorize(self, document_id, agent_id):
        if not self.check(document_id, agent_id):
            raise KnowledgeAccessDeniedError(
                f"agent {agent_id!r} cannot access knowledge {document_id!r}"
            )


__all__ = ["KnowledgeAccessPolicy", "KnowledgeAccessControl"]
