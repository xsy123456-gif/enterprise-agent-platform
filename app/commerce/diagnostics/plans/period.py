"""Period resolution.

A plan's ``analysis_period`` / ``comparison_period`` are date-free
*specifications* (e.g. ``{"days": 7}``).  The resolved ``TimeRange`` is computed
at execution time from the runtime ``now`` and belongs to execution input/state
— concrete dates are never frozen into the plan version.

Resolution is strictly timezone-aware: naive datetimes and implicit system
timezone are rejected; the resolved ``TimeRange`` preserves timezone and
boundary-policy metadata.
"""

from datetime import datetime, timedelta, timezone

from app.commerce.contracts.query import TimeRange


def _as_aware_datetime(value):
    if isinstance(value, datetime):
        current = value
    elif isinstance(value, str):
        current = datetime.fromisoformat(value)
    else:
        raise ValueError("now must be a datetime or an ISO-8601 string")
    if current.tzinfo is None:
        raise ValueError("now must be timezone-aware; naive datetime is not allowed")
    return current


def _require_aware(value):
    if value is None:
        return
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise ValueError("timestamps must be datetime or ISO-8601 strings")
    if parsed.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return parsed


def resolve_period(spec, now):
    """Resolve a period spec into a timezone-aware ``TimeRange``.

    - ``None`` / ``{}`` -> open TimeRange (unbounded);
    - ``{"days": N}`` -> last N days ending at ``now`` (which must be aware);
    - ``{"start": ..., "end": ...}`` -> explicit window (execution input; the
      timestamps must be timezone-aware).
    """
    spec = spec or {}
    timezone_name = spec.get("timezone", "UTC")
    boundary_policy = spec.get("boundary_policy", "INCLUSIVE")
    if "start" in spec or "end" in spec:
        _require_aware(spec.get("start"))
        _require_aware(spec.get("end"))
        return TimeRange(start=spec.get("start"), end=spec.get("end"),
                         timezone=timezone_name, boundary_policy=boundary_policy)
    days = spec.get("days")
    if days is None:
        return TimeRange(timezone=timezone_name, boundary_policy=boundary_policy)
    current = _as_aware_datetime(now)
    end = current.isoformat()
    start = (current - timedelta(days=int(days))).isoformat()
    return TimeRange(start=start, end=end, timezone=timezone_name,
                     boundary_policy=boundary_policy)


__all__ = ["resolve_period"]
