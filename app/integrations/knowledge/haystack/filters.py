"""EffectiveFilter -> Qdrant filter mapping.

The mandatory ACL filter is produced here *before* retrieval.  Field names map
onto Qdrant payload keys (Haystack stores document meta under ``meta.*``).

Optional ACL dimensions (store / region / department) use ``IS NULL OR IN``
semantics: a document without that dimension is treated as global (visible to
everyone subject to the mandatory dimensions).  Mandatory dimensions (tenant,
security level, knowledge scope) always match.
"""

from typing import Any

from qdrant_client import models

from app.knowledge.access.filters import EffectiveFilter

from .config import HaystackKnowledgeConfig


def _eq(field, value):
    return models.FieldCondition(key=field, match=models.MatchValue(value=value))


def _in(field, values):
    return models.FieldCondition(key=field, match=models.MatchAny(any=list(values)))


def _null_or_in(field, values):
    """IS NULL (global) OR IN (scoped)."""
    if not values:
        return None
    return models.Filter(
        should=[
            models.FieldCondition(key=field, is_null=True),
            _in(field, values),
        ]
    )


def build_filter(
    effective_filter: EffectiveFilter,
    config: HaystackKnowledgeConfig,
) -> models.Filter:
    """Build the mandatory retrieval filter (ACL + authorized scope)."""

    must: list[Any] = []

    # --- mandatory (authorization) ---
    must.append(_eq("meta.tenant_id", effective_filter.tenant_id))
    allowed_levels = config.allowed_levels(effective_filter.security_level)
    must.append(_in("meta.security_level", allowed_levels))

    # --- optional ACL dimensions (global OR scoped) ---
    for field, values in (
        ("meta.store_id", effective_filter.stores),
        ("meta.region", effective_filter.regions),
        ("meta.department_id", effective_filter.departments),
    ):
        condition = _null_or_in(field, values)
        if condition is not None:
            must.append(condition)

    # --- authorized knowledge scope (mandatory when set) ---
    if effective_filter.knowledge_types:
        must.append(_in("meta.knowledge_type", effective_filter.knowledge_types))

    # --- requested business filters (non-authoritative, already intersected) ---
    for key, value in (effective_filter.extra or {}).items():
        must.append(_eq(f"meta.{key}", value))

    return models.Filter(must=must)
