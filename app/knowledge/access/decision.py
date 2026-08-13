"""Knowledge policy decision models.

Knowledge retrieval uses light governance: ALLOW / DENY only.  No human
approval for ordinary knowledge reads.
"""

from dataclasses import dataclass
from enum import Enum


class KnowledgePolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class KnowledgePolicyResult:
    decision: KnowledgePolicyDecision
    reason: str = ""

    @property
    def allowed(self):
        return self.decision is KnowledgePolicyDecision.ALLOW
