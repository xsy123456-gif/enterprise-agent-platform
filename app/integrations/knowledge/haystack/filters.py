"""EffectiveFilter -> Haystack/Qdrant filter mapping.

The mandatory ACL filter is produced here *before* retrieval.  Field names map
onto Qdrant payload keys (Haystack stores document meta under ``meta.*``).
ACL fields and business-scope fields are intentionally listed separately so
authorization can never be confused with a consumer preference.
"""

from typing import Any

from app.knowledge.access.filters import EffectiveFilter

from .config import HaystackKnowledgeConfig


def _eq(field, value):
    return {"field": field, "operator": "==", "value": value}


def _in(field, values):
    return {"field": field, "operator": "in", "value": list(values)}


def build_filter(
    effective_filter: EffectiveFilter,
    config: HaystackKnowledgeConfig,
) -> dict[str, Any] | None:
    """Build the mandatory retrieval filter (ACL + authorized scope)."""

    conditions: list[dict[str, Any]] = []

    # --- ACL (authorization) ---
    conditions.append(_eq("meta.tenant_id", effective_filter.tenant_id))

    allowed_levels = config.allowed_levels(effective_filter.security_level)
    conditions.append(_in("meta.security_level", allowed_levels))

    if effective_filter.stores:
        conditions.append(_in("meta.store_id", effective_filter.stores))
    if effective_filter.regions:
        conditions.append(_in("meta.region", effective_filter.regions))
    if effective_filter.departments:
        conditions.append(_in("meta.department_id", effective_filter.departments))

    # --- authorized knowledge scope ---
    if effective_filter.knowledge_types:
        conditions.append(
            _in("meta.knowledge_type", effective_filter.knowledge_types)
        )

    # --- requested business filters (non-authoritative, already intersected) ---
    for key, value in (effective_filter.extra or {}).items():
        conditions.append(_eq(f"meta.{key}", value))

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"operator": "AND", "conditions": conditions}
