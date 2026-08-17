"""Commerce query layer.

The Query Service is the single read boundary above the canonical store.  It
always enforces the *trusted* tenant id (from the execution context, never from
caller-supplied data) and attaches freshness / quality / provenance metadata to
every ``QueryResult``.
"""

from app.commerce.query.freshness import FreshnessPolicy, evaluate_freshness
from app.commerce.query.provenance import canonical_provenance
from app.commerce.query.service import CommerceQueryService

__all__ = [
    "CommerceQueryService",
    "FreshnessPolicy",
    "evaluate_freshness",
    "canonical_provenance",
]
