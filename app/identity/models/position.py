"""Position — tenant-owned enterprise entity.

Position (organizational job) is distinct from Role (permission grouping).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    position_id: str
    tenant_id: str
    name: str
