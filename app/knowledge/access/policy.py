"""Knowledge access policy — default deny.

Any access that cannot be explicitly proven allowed is denied (fail closed):
missing tenant, missing required ACL, unknown security level, malformed ACL,
unsupported scope.
"""

from app.knowledge.access.decision import (
    KnowledgePolicyDecision,
    KnowledgePolicyResult,
)
from app.knowledge.access.filters import EffectiveFilter
from app.knowledge.models.access import KnowledgeAccessContext


class KnowledgePolicy:
    """Enforce the mandatory authorization invariants."""

    def evaluate(
        self,
        access_context: KnowledgeAccessContext,
        effective_filter: EffectiveFilter,
    ) -> KnowledgePolicyResult:
        if not access_context.tenant_id:
            return KnowledgePolicyResult(
                KnowledgePolicyDecision.DENY, "missing tenant"
            )
        if effective_filter.tenant_id != access_context.tenant_id:
            return KnowledgePolicyResult(
                KnowledgePolicyDecision.DENY, "tenant mismatch"
            )
        if not access_context.security_clearance:
            return KnowledgePolicyResult(
                KnowledgePolicyDecision.DENY, "missing security clearance"
            )
        return KnowledgePolicyResult(KnowledgePolicyDecision.ALLOW, "ok")
