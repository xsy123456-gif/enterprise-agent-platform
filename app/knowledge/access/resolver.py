"""Scope / ACL resolution.

Produces the mandatory effective filter *before* retrieval.  Tenant isolation
is enforced here and cannot be influenced by the consumer: ``tenant_id`` always
comes from the trusted ``KnowledgeAccessContext``.
"""

from app.knowledge.access.filters import EffectiveFilter, intersect_lists
from app.knowledge.errors import KnowledgeAccessDeniedError
from app.knowledge.models.access import KnowledgeAccessContext
from app.knowledge.models.request import KnowledgeRetrieveRequest


class ScopeResolver:
    """Resolve requested business filters against the authorized scope."""

    def resolve(
        self,
        request: KnowledgeRetrieveRequest,
        access_context: KnowledgeAccessContext,
    ) -> EffectiveFilter:
        tenant_id = access_context.tenant_id

        knowledge_types = intersect_lists(
            request.knowledge_types, access_context.authorized_knowledge_scopes
        )

        business = request.business_filters or {}

        stores = intersect_lists(
            self._as_list(business.get("store_ids")),
            access_context.authorized_store_ids,
        )

        regions = intersect_lists(
            self._as_list(business.get("regions")),
            access_context.authorized_regions,
        )

        departments = intersect_lists(
            self._as_list(business.get("department_ids")),
            (access_context.department_id,)
            if access_context.department_id
            else (),
        )

        # A requested dimension that resolves to empty after intersection means
        # the consumer asked for something it is not authorized to see.  Fail
        # closed rather than silently widening scope.
        if any(
            self._requested_but_empty(business.get(key), resolved)
            for key, resolved in (
                ("store_ids", stores),
                ("regions", regions),
                ("department_ids", departments),
            )
        ):
            raise KnowledgeAccessDeniedError(
                "Requested scope is not authorized"
            )

        if knowledge_types is not None and not knowledge_types and request.knowledge_types:
            raise KnowledgeAccessDeniedError(
                "Requested knowledge types are not authorized"
            )

        return EffectiveFilter(
            tenant_id=tenant_id,
            knowledge_types=knowledge_types or (),
            regions=regions or (),
            stores=stores or (),
            departments=departments or (),
            security_level=access_context.security_clearance,
            extra={
                key: value
                for key, value in business.items()
                if key not in {"store_ids", "regions", "department_ids"}
            },
        )

    @staticmethod
    def _as_list(value):
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            return list(value)
        return [value]

    @staticmethod
    def _requested_but_empty(requested, resolved):
        return requested is not None and not resolved
