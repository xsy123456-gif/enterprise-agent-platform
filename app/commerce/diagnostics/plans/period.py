"""Period resolution.

A plan's ``analysis_period`` / ``comparison_period`` are date-free
*specifications* (e.g. ``{"days": 7}``).  The resolved ``TimeRange`` is computed
at execution time from the runtime ``now`` and belongs to execution input/state
— concrete dates are never frozen into the plan version.
"""

from datetime import datetime, timedelta, timezone

from app.commerce.contracts.query import TimeRange


def resolve_period(spec, now):
    """Resolve a period spec into a ``TimeRange``.

    - ``None`` / ``{}`` -> open TimeRange (unbounded);
    - ``{"days": N}`` -> last N days ending at ``now``;
    - ``{"start": ..., "end": ...}`` -> explicit window (used only when the
      runtime supplies explicit dates as execution input, not from the plan).
    """
    spec = spec or {}
    if "start" in spec or "end" in spec:
        return TimeRange(start=spec.get("start"), end=spec.get("end"),
                         timezone=spec.get("timezone", "UTC"))
    days = spec.get("days")
    if days is None:
        return TimeRange()
    current = now if isinstance(now, datetime) else datetime.fromisoformat(str(now))
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    end = current.isoformat()
    start = (current - timedelta(days=int(days))).isoformat()
    return TimeRange(start=start, end=end, timezone="UTC")


__all__ = ["resolve_period"]
