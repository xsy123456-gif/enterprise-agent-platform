"""Optimization pattern detection (Phase 17.2).

Detects issues from evaluation data (performance / cost / quality / feedback) —
data-driven, never an LLM guess.
"""

from dataclasses import dataclass, field

ISSUE_PERFORMANCE = "performance"
ISSUE_COST = "cost"
ISSUE_QUALITY = "quality"
ISSUE_FEEDBACK = "feedback"
ISSUE_TYPES = frozenset({ISSUE_PERFORMANCE, ISSUE_COST, ISSUE_QUALITY,
                         ISSUE_FEEDBACK})


@dataclass(frozen=True)
class DetectedIssue:
    issue_type: str
    message: str
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "evidence", dict(self.evidence or {}))
        if self.issue_type not in ISSUE_TYPES:
            raise ValueError(f"unknown issue type: {self.issue_type}")


class PatternDetector:

    def __init__(self, failure_rate_threshold=0.2, cost_threshold=1.0):
        self.failure_rate_threshold = failure_rate_threshold
        self.cost_threshold = cost_threshold

    def detect(self, evaluation) -> list[DetectedIssue]:
        metrics = evaluation.metrics or {}
        issues = []
        failure_rate = metrics.get("failure_rate", 0.0)
        if failure_rate > self.failure_rate_threshold:
            issues.append(DetectedIssue(
                issue_type=ISSUE_PERFORMANCE,
                message=f"failure rate {failure_rate:.2%} exceeds threshold "
                        f"{self.failure_rate_threshold:.0%}",
                evidence={"failure_rate": failure_rate},
            ))
        avg_cost = metrics.get("avg_cost", 0.0)
        if avg_cost > self.cost_threshold:
            issues.append(DetectedIssue(
                issue_type=ISSUE_COST,
                message=f"avg cost {avg_cost} exceeds threshold "
                        f"{self.cost_threshold}",
                evidence={"avg_cost": avg_cost},
            ))
        if evaluation.feedback is not None and evaluation.feedback < 3.0:
            issues.append(DetectedIssue(
                issue_type=ISSUE_FEEDBACK,
                message=f"low feedback score {evaluation.feedback}",
                evidence={"feedback": evaluation.feedback},
            ))
        return issues


__all__ = [
    "PatternDetector",
    "DetectedIssue",
    "ISSUE_TYPES",
    "ISSUE_PERFORMANCE",
    "ISSUE_COST",
    "ISSUE_QUALITY",
    "ISSUE_FEEDBACK",
]
