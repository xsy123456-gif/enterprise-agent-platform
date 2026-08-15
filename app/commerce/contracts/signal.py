"""Signal contract.

A Signal is the output of anomaly / trend detection: a status + direction for a
subject, with references to supporting Evidence.  A Signal must NOT carry a
root cause — cause reasoning happens in the Rule Engine (``Cause``).
"""

from dataclasses import dataclass, field

from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.subject import SubjectRef

SIGNAL_NORMAL = "NORMAL"
SIGNAL_WARNING = "WARNING"
SIGNAL_ABNORMAL = "ABNORMAL"
SIGNAL_CRITICAL = "CRITICAL"
SIGNAL_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
SIGNAL_UNKNOWN = "UNKNOWN"
SIGNAL_NOT_APPLICABLE = "NOT_APPLICABLE"
SIGNAL_STATUSES = frozenset({
    SIGNAL_NORMAL,
    SIGNAL_WARNING,
    SIGNAL_ABNORMAL,
    SIGNAL_CRITICAL,
    SIGNAL_INSUFFICIENT_DATA,
    SIGNAL_UNKNOWN,
    SIGNAL_NOT_APPLICABLE,
})

DIRECTION_UP = "UP"
DIRECTION_DOWN = "DOWN"
DIRECTION_STABLE = "STABLE"
DIRECTION_NONE = "NONE"
DIRECTIONS = frozenset({DIRECTION_UP, DIRECTION_DOWN, DIRECTION_STABLE, DIRECTION_NONE})


@dataclass(frozen=True)
class Signal:
    signal_id: str
    signal_code: str
    domain: str
    subject: SubjectRef
    status: str = SIGNAL_UNKNOWN
    direction: str = DIRECTION_NONE
    magnitude: float | None = None
    anomaly_score: float | None = None
    evidence_ids: tuple[str, ...] = ()
    detection_method: str = ""
    algorithm_version: str = ""
    policy_version: str = ""
    detected_at: str = ""

    def __post_init__(self):
        object.__setattr__(self, "evidence_ids", tuple(self.evidence_ids or ()))
        if self.status not in SIGNAL_STATUSES:
            raise CommerceValidationError(f"unknown signal status: {self.status}")
        if self.direction not in DIRECTIONS:
            raise CommerceValidationError(f"unknown signal direction: {self.direction}")

    def to_dict(self) -> dict:
        return {
            "signal_id": self.signal_id,
            "signal_code": self.signal_code,
            "domain": self.domain,
            "subject": self.subject.to_dict(),
            "status": self.status,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "anomaly_score": self.anomaly_score,
            "evidence_ids": list(self.evidence_ids),
            "detection_method": self.detection_method,
            "algorithm_version": self.algorithm_version,
            "policy_version": self.policy_version,
            "detected_at": self.detected_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Signal":
        return cls(
            signal_id=data["signal_id"],
            signal_code=data["signal_code"],
            domain=data["domain"],
            subject=SubjectRef.from_dict(data["subject"]),
            status=data.get("status", SIGNAL_UNKNOWN),
            direction=data.get("direction", DIRECTION_NONE),
            magnitude=data.get("magnitude"),
            anomaly_score=data.get("anomaly_score"),
            evidence_ids=tuple(data.get("evidence_ids", ())),
            detection_method=data.get("detection_method", ""),
            algorithm_version=data.get("algorithm_version", ""),
            policy_version=data.get("policy_version", ""),
            detected_at=data.get("detected_at", ""),
        )


__all__ = [
    "Signal",
    "SIGNAL_STATUSES",
    "SIGNAL_NORMAL",
    "SIGNAL_WARNING",
    "SIGNAL_ABNORMAL",
    "SIGNAL_CRITICAL",
    "SIGNAL_INSUFFICIENT_DATA",
    "SIGNAL_UNKNOWN",
    "SIGNAL_NOT_APPLICABLE",
    "DIRECTIONS",
    "DIRECTION_UP",
    "DIRECTION_DOWN",
    "DIRECTION_STABLE",
    "DIRECTION_NONE",
]
