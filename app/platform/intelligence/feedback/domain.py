"""Agent feedback model (Phase 17.5)."""

from dataclasses import dataclass

FB_WRONG_DIAGNOSIS = "WRONG_DIAGNOSIS"
FB_MISSING_INFORMATION = "MISSING_INFORMATION"
FB_INCORRECT_ACTION = "INCORRECT_ACTION"
FB_TOO_EXPENSIVE = "TOO_EXPENSIVE"
FB_GOOD_RESULT = "GOOD_RESULT"
FEEDBACK_CATEGORIES = frozenset({
    FB_WRONG_DIAGNOSIS, FB_MISSING_INFORMATION, FB_INCORRECT_ACTION,
    FB_TOO_EXPENSIVE, FB_GOOD_RESULT,
})


@dataclass(frozen=True)
class AgentFeedback:
    feedback_id: str
    execution_id: str = ""
    user_id: str = ""
    rating: float = 0.0
    comment: str = ""
    correction: str = ""
    category: str = FB_GOOD_RESULT

    def __post_init__(self):
        if not self.feedback_id:
            raise ValueError("feedback_id is required")
        if self.category not in FEEDBACK_CATEGORIES:
            raise ValueError(f"unknown feedback category: {self.category}")

    def to_dict(self) -> dict:
        return {
            "feedback_id": self.feedback_id,
            "execution_id": self.execution_id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "correction": self.correction,
            "category": self.category,
        }


__all__ = [
    "AgentFeedback",
    "FEEDBACK_CATEGORIES",
    "FB_WRONG_DIAGNOSIS",
    "FB_MISSING_INFORMATION",
    "FB_INCORRECT_ACTION",
    "FB_TOO_EXPENSIVE",
    "FB_GOOD_RESULT",
]
