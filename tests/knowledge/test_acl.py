"""Phase 4 ACL / scope unit tests (no backend required)."""

import unittest

from app.knowledge import (
    KnowledgeAccessContext,
    KnowledgeAccessDeniedError,
    KnowledgeConfig,
    KnowledgeRetrieveRequest,
    KnowledgeService,
    KnowledgeRetrieverPort,
    KnowledgeQuery,
    KnowledgeRetrieval,
)
from app.knowledge.access import (
    KnowledgePolicy,
    KnowledgePolicyDecision,
    KnowledgePolicyResult,
    ScopeResolver,
)


class _RecordingRetriever(KnowledgeRetrieverPort):
    def __init__(self):
        self.queries = []

    async def retrieve(self, query: KnowledgeQuery) -> KnowledgeRetrieval:
        self.queries.append(query)
        return KnowledgeRetrieval(hits=[])


def _ctx(**kw):
    base = dict(
        tenant_id="tenant_A",
        user_id="u1",
        role="sales",
        authorized_store_ids=("JP01", "JP02"),
        authorized_regions=("JP",),
        authorized_knowledge_scopes=("policy", "faq"),
        security_clearance="internal",
    )
    base.update(kw)
    return KnowledgeAccessContext(**base)


class ScopeResolverTest(unittest.TestCase):
    def setUp(self):
        self.resolver = ScopeResolver()

    def test_tenant_comes_from_access_context_not_request(self):
        f = self.resolver.resolve(
            KnowledgeRetrieveRequest(query="q", business_filters={"tenant_id": "tenant_B"}),
            _ctx(),
        )
        self.assertEqual("tenant_A", f.tenant_id)

    def test_store_intersection(self):
        f = self.resolver.resolve(
            KnowledgeRetrieveRequest(query="q", business_filters={"store_ids": ["JP01"]}),
            _ctx(),
        )
        self.assertEqual(("JP01",), f.stores)

    def test_unauthorized_store_is_denied(self):
        with self.assertRaises(KnowledgeAccessDeniedError):
            self.resolver.resolve(
                KnowledgeRetrieveRequest(query="q", business_filters={"store_ids": ["JP99"]}),
                _ctx(),
            )

    def test_wildcard_store_is_denied(self):
        with self.assertRaises(KnowledgeAccessDeniedError):
            self.resolver.resolve(
                KnowledgeRetrieveRequest(query="q", business_filters={"store_ids": ["*"]}),
                _ctx(),
            )

    def test_unauthorized_knowledge_type_is_denied(self):
        with self.assertRaises(KnowledgeAccessDeniedError):
            self.resolver.resolve(
                KnowledgeRetrieveRequest(query="q", knowledge_types=["management"]),
                _ctx(),
            )

    def test_region_intersection(self):
        f = self.resolver.resolve(
            KnowledgeRetrieveRequest(query="q", business_filters={"regions": ["JP"]}),
            _ctx(),
        )
        self.assertEqual(("JP",), f.regions)

    def test_unknown_region_is_denied(self):
        with self.assertRaises(KnowledgeAccessDeniedError):
            self.resolver.resolve(
                KnowledgeRetrieveRequest(query="q", business_filters={"regions": ["US"]}),
                _ctx(),
            )

    def test_security_clearance_passed_through(self):
        f = self.resolver.resolve(KnowledgeRetrieveRequest(query="q"), _ctx())
        self.assertEqual("internal", f.security_level)


class KnowledgePolicyTest(unittest.TestCase):
    def setUp(self):
        self.policy = KnowledgePolicy()

    def test_missing_tenant_rejected_at_context_construction(self):
        # KnowledgeAccessContext fails fast on empty tenant (default deny).
        with self.assertRaises(ValueError):
            KnowledgeAccessContext(tenant_id="", user_id="u1")

    def test_tenant_mismatch_denied(self):
        from app.knowledge.access.filters import EffectiveFilter
        result = self.policy.evaluate(
            _ctx(), EffectiveFilter(tenant_id="tenant_B")
        )
        self.assertFalse(result.allowed)

    def test_valid_allow(self):
        from app.knowledge.access.filters import EffectiveFilter
        result = self.policy.evaluate(
            _ctx(), EffectiveFilter(tenant_id="tenant_A", security_level="internal")
        )
        self.assertTrue(result.allowed)
        self.assertEqual(KnowledgePolicyDecision.ALLOW, result.decision)


if __name__ == "__main__":
    unittest.main()
