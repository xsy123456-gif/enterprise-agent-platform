"""Attributes — extension bag for non-core identity facts.

Core facts (department/position/level/role/scope/clearance) must use their
dedicated models; only genuinely non-core facts belong here.
"""

from typing import Any

Attributes = dict[str, Any]
