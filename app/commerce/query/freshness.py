"""Freshness evaluation.

Freshness is a property of *data*, distinct from data quality.  A record is
FRESH / STALE / REFRESHED / UNKNOWN relative to a ``FreshnessPolicy``; the TTL
is policy-owned (not frozen as a fixed number by this layer).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from app.commerce.contracts.query import (
    FRESHNESS_FRESH,
    FRESHNESS_STALE,
    FRESHNESS_UNKNOWN,
    FreshnessMetadata,
)


@dataclass(frozen=True)
class FreshnessPolicy:
    policy_id: str
    version: str = "1.0"
    ttl_seconds: float | None = None


STANDARD_READ_POLICY = FreshnessPolicy("commerce.standard_read.v1", "1.0", None)


def _parse_iso(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def age_seconds(observed_at, now):
    observed = _parse_iso(observed_at)
    current = _parse_iso(now) or datetime.now(timezone.utc)
    if observed is None or current is None:
        return None
    return (current - observed).total_seconds()


def evaluate_freshness(policy, last_synced_at, observed_at=None, now=None):
    """Compute ``FreshnessMetadata`` for a record against a policy."""
    current = _parse_iso(now) or datetime.now(timezone.utc)
    if last_synced_at is None:
        return FreshnessMetadata(
            status=FRESHNESS_UNKNOWN,
            observed_at=observed_at,
            policy_id=policy.policy_id,
            policy_version=policy.version,
        )
    age = age_seconds(last_synced_at, current)
    status = FRESHNESS_FRESH
    if policy.ttl_seconds is not None and (age is None or age > policy.ttl_seconds):
        status = FRESHNESS_STALE
    return FreshnessMetadata(
        status=status,
        observed_at=observed_at,
        last_synced_at=last_synced_at,
        policy_id=policy.policy_id,
        policy_version=policy.version,
        age_seconds=age,
    )


__all__ = ["FreshnessPolicy", "STANDARD_READ_POLICY", "evaluate_freshness", "age_seconds"]
