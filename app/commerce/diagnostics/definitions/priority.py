"""PriorityPolicy definition — versioned priority scoring.

Priority is NOT severity: severity is one of five weighted inputs.  The policy
defines the factor weights and the P0/P1/P2/P3 score thresholds; the
PriorityEngine only executes the weighted sum and threshold mapping.
"""

from dataclasses import dataclass, field

PRIORITY_FACTORS = ("severity", "business_impact", "urgency", "confidence", "actionability")


@dataclass(frozen=True)
class PriorityPolicy:
    policy_id: str
    version: str
    weights: dict[str, float] = field(default_factory=lambda: {
        "severity": 0.30,
        "business_impact": 0.25,
        "urgency": 0.20,
        "confidence": 0.15,
        "actionability": 0.10,
    })
    p0_threshold: float = 0.85
    p1_threshold: float = 0.65
    p2_threshold: float = 0.45

    def __post_init__(self):
        object.__setattr__(self, "weights", dict(self.weights or {}))

    def weight_for(self, factor):
        return self.weights.get(factor, 0.0)

    def to_dict(self) -> dict:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "weights": dict(self.weights),
            "p0_threshold": self.p0_threshold,
            "p1_threshold": self.p1_threshold,
            "p2_threshold": self.p2_threshold,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PriorityPolicy":
        return cls(
            policy_id=data["policy_id"],
            version=data["version"],
            weights=data.get("weights", {
                "severity": 0.30, "business_impact": 0.25, "urgency": 0.20,
                "confidence": 0.15, "actionability": 0.10,
            }),
            p0_threshold=data.get("p0_threshold", 0.85),
            p1_threshold=data.get("p1_threshold", 0.65),
            p2_threshold=data.get("p2_threshold", 0.45),
        )


__all__ = ["PriorityPolicy", "PRIORITY_FACTORS"]
