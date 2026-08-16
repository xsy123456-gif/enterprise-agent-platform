"""Extraction quality evaluation (Phase 11.7).

Two v1 layers only:

1. Schema validation — fields, types, ranges.
2. Consistency validation — source text vs result.

Business evaluation is deferred: ReviewInsight never computes cause / impact /
priority, so the evaluator only reports ``business_evaluation = DEFERRED``.
"""

from dataclasses import dataclass

EVAL_VALID = "VALID"
EVAL_SCHEMA_INVALID = "SCHEMA_INVALID"
EVAL_INCONSISTENT = "INCONSISTENT"
EVAL_STATUSES = frozenset({EVAL_VALID, EVAL_SCHEMA_INVALID, EVAL_INCONSISTENT})
BUSINESS_DEFERRED = "DEFERRED"

_SCALAR_STRINGS = ("sentiment", "severity", "intent")
_SEQUENCE_STRINGS = ("topics", "issues", "strengths")


@dataclass(frozen=True)
class ExtractionEvaluationResult:
    status: str
    schema_valid: bool
    consistency_valid: bool
    schema_issues: tuple[str, ...] = ()
    consistency_issues: tuple[str, ...] = ()
    business_evaluation: str = BUSINESS_DEFERRED

    def __post_init__(self):
        object.__setattr__(self, "schema_issues", tuple(self.schema_issues or ()))
        object.__setattr__(self, "consistency_issues", tuple(self.consistency_issues or ()))

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "schema_valid": self.schema_valid,
            "consistency_valid": self.consistency_valid,
            "schema_issues": list(self.schema_issues),
            "consistency_issues": list(self.consistency_issues),
            "business_evaluation": self.business_evaluation,
        }


class ExtractionEvaluation:

    def evaluate(self, result, review=None) -> ExtractionEvaluationResult:
        schema_issues = self._schema_issues(result)
        consistency_issues = self._consistency_issues(result, review)
        schema_valid = not schema_issues
        consistency_valid = not consistency_issues
        if not schema_valid:
            status = EVAL_SCHEMA_INVALID
        elif not consistency_valid:
            status = EVAL_INCONSISTENT
        else:
            status = EVAL_VALID
        return ExtractionEvaluationResult(
            status=status,
            schema_valid=schema_valid,
            consistency_valid=consistency_valid,
            schema_issues=schema_issues,
            consistency_issues=consistency_issues,
            business_evaluation=BUSINESS_DEFERRED,
        )

    @staticmethod
    def _schema_issues(result):
        issues = []
        if not isinstance(getattr(result, "review_id", None), str) or not result.review_id:
            issues.append("review_id must be a non-empty string")
        confidence = getattr(result, "confidence", None)
        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                issues.append("confidence must be a number")
            elif not (0.0 <= confidence <= 1.0):
                issues.append("confidence out of range [0, 1]")
        for field in _SCALAR_STRINGS:
            value = getattr(result, field, None)
            if value is not None and not isinstance(value, str):
                issues.append(f"{field} must be a string")
        for field in _SEQUENCE_STRINGS:
            value = getattr(result, field, ())
            if not isinstance(value, (tuple, list)):
                issues.append(f"{field} must be a list of strings")
            elif not all(isinstance(v, str) for v in value):
                issues.append(f"{field} must contain only strings")
        return tuple(issues)

    @staticmethod
    def _consistency_issues(result, review):
        if review is None:
            return ()
        issues = []
        rating = getattr(review, "rating", None)
        text = " ".join(
            part for part in (
                getattr(review, "title", None) or "",
                getattr(review, "content", None) or "",
            )
        ).strip()
        if isinstance(rating, (int, float)) and rating > 0:
            sentiment = getattr(result, "sentiment", "") or ""
            if sentiment == "negative" and rating >= 4:
                issues.append(f"negative sentiment contradicts rating {rating}")
            if sentiment == "positive" and rating <= 2:
                issues.append(f"positive sentiment contradicts rating {rating}")
        if getattr(result, "issues", ()) and not text:
            issues.append("issues extracted but source text is empty")
        confidence = getattr(result, "confidence", None)
        if confidence is not None and confidence >= 0.9:
            if not any((getattr(result, "sentiment", ""),
                        getattr(result, "issues", ()),
                        getattr(result, "topics", ()))):
                issues.append("high confidence with no extracted signals")
        return tuple(issues)


__all__ = [
    "ExtractionEvaluation",
    "ExtractionEvaluationResult",
    "EVAL_VALID",
    "EVAL_SCHEMA_INVALID",
    "EVAL_INCONSISTENT",
    "EVAL_STATUSES",
    "BUSINESS_DEFERRED",
]
