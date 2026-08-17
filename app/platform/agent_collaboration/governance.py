"""Collaboration governance (Phase 14.6).

Enterprise rules over which agent may delegate to which, with per-edge depth
and cost limits.  Fail-closed: no matching policy -> deny.
"""

from dataclasses import dataclass, field

from app.platform.agent_collaboration.errors import DelegationDeniedError


@dataclass(frozen=True)
class AgentCollaborationPolicy:
    policy_id: str
    source_agent: str
    target_agent: str
    allowed: bool = True
    max_depth: int = 3
    max_cost: float = 0.0
    allowed_context_types: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "allowed_context_types",
                           tuple(self.allowed_context_types or ()))
        if not self.source_agent:
            raise ValueError("source_agent is required")
        if not self.target_agent:
            raise ValueError("target_agent is required")


class CollaborationAccessControl:

    def __init__(self, policies=None):
        self._policies = list(policies or [])

    def add_policy(self, policy):
        self._policies.append(policy)
        return policy

    def _policy(self, source_agent, target_agent):
        for policy in self._policies:
            if (policy.source_agent == source_agent
                    and policy.target_agent == target_agent):
                return policy
        return None

    def check(self, source_agent, target_agent) -> bool:
        policy = self._policy(source_agent, target_agent)
        return bool(policy and policy.allowed)

    def authorize(self, source_agent, target_agent):
        if not self.check(source_agent, target_agent):
            raise DelegationDeniedError(
                f"delegation {source_agent!r} -> {target_agent!r} is not allowed"
            )

    def allowed_delegations(self):
        return {
            (p.source_agent, p.target_agent)
            for p in self._policies if p.allowed
        }

    def max_depth(self, source_agent, target_agent, default=3):
        policy = self._policy(source_agent, target_agent)
        return policy.max_depth if policy else default

    def max_cost(self, source_agent, target_agent, default=0.0):
        policy = self._policy(source_agent, target_agent)
        return policy.max_cost if policy else default


__all__ = ["AgentCollaborationPolicy", "CollaborationAccessControl"]
