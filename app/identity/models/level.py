"""Professional level — platform-level public enum (P1-P10).

P level is a professional-grading fact, NOT a permission.  Authorization
decisions are made by the Permission/Governance layers, never here.
"""

from enum import Enum


class ProfessionalLevel(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"
    P7 = "P7"
    P8 = "P8"
    P9 = "P9"
    P10 = "P10"

    @classmethod
    def values(cls):
        return [item.value for item in cls]
