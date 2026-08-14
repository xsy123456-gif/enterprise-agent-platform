"""Security clearance — platform-level public enum.

A person's security clearance is an enterprise identity fact in its own right,
independent of professional level and of any downstream consumer.
"""

from enum import Enum


class SecurityClearance(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

    @classmethod
    def values(cls):
        return [item.value for item in cls]
