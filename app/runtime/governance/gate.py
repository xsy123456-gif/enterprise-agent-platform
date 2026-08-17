"""Backend-neutral governance boundary for runtime side effects."""

from dataclasses import dataclass
from enum import Enum


class GovernanceDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


@dataclass(frozen=True)
class GovernanceResult:
    decision: GovernanceDecision
    reason: str = ""
    approval_id: str | None = None


class AllowAllGovernancePolicy:
    def evaluate(self, request):
        return GovernanceResult(GovernanceDecision.ALLOW, "default policy")


class DenyByDefaultGovernancePolicy:
    """Fail-closed production default: deny unless an explicit policy allows."""

    def evaluate(self, request):
        return GovernanceResult(GovernanceDecision.DENY, "no policy configured")


class GovernanceGate:
    """Every governed runtime action enters here before execution."""

    def __init__(self, policy=None, event_bus=None):
        self.policy = policy or AllowAllGovernancePolicy()
        self.event_bus = event_bus

    def evaluate(self, request):
        result = self.policy.evaluate(request)
        if not isinstance(result, GovernanceResult):
            result = GovernanceResult(GovernanceDecision(result))
        if self.event_bus is not None:
            from app.events.models import Event
            self.event_bus.publish(Event("governance.checked", {
                "execution_id": getattr(request, "execution_id", None),
                "agent_id": getattr(request, "agent_id", None),
                "tool": getattr(request, "tool_name", None),
                "decision": result.decision.value,
            }))
        return result

    def check(self, request):
        result = self.evaluate(request)
        if result.decision is not GovernanceDecision.ALLOW:
            return False, result
        return True, result
