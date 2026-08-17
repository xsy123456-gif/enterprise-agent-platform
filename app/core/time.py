"""Platform-common time primitives (Phase 18.6).

The single ``utc_now()`` used by both Platform and Commerce.  Commerce
re-exports this; no Platform module imports time from Commerce.
"""

from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = ["utc_now"]
