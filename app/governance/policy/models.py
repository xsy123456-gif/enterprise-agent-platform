from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PolicyRule:
    subject: str
    action: str
    resource: str
    effect: str


@dataclass
class GovernancePolicy:
    policy_id: str
    name: str
    rules: list[PolicyRule] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)


@dataclass
class PolicyRequest:
    user_id: str
    role: str
    action: str
    agent_id: str
    version: str

    @property
    def resource(self):
        return f"{self.agent_id}:{self.version}"


@dataclass
class PolicyDecision:
    decision: str
    reason: str

    @property
    def allowed(self):
        return self.decision == "allow"
