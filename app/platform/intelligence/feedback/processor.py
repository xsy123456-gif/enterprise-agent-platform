"""Feedback processor (Phase 17.5).

Turns user feedback into an optimization signal: negative categories become
optimization signals, positive categories become positive signals.  Feedback
never directly changes an agent.
"""

from dataclasses import dataclass

from app.platform.intelligence.feedback.domain import (
    FB_GOOD_RESULT,
    FB_INCORRECT_ACTION,
    FB_MISSING_INFORMATION,
    FB_TOO_EXPENSIVE,
    FB_WRONG_DIAGNOSIS,
    AgentFeedback,
)

_NEGATIVE_CATEGORIES = frozenset({
    FB_WRONG_DIAGNOSIS, FB_MISSING_INFORMATION, FB_INCORRECT_ACTION,
    FB_TOO_EXPENSIVE,
})


@dataclass(frozen=True)
class FeedbackSignal:
    feedback_id: str
    category: str
    negative: bool
    message: str

    def to_dict(self) -> dict:
        return {
            "feedback_id": self.feedback_id,
            "category": self.category,
            "negative": self.negative,
            "message": self.message,
        }


class FeedbackProcessor:

    def __init__(self):
        self.signals = []

    def process(self, feedback: AgentFeedback) -> FeedbackSignal:
        negative = feedback.category in _NEGATIVE_CATEGORIES
        signal = FeedbackSignal(
            feedback_id=feedback.feedback_id, category=feedback.category,
            negative=negative,
            message=feedback.correction or feedback.comment,
        )
        self.signals.append(signal)
        return signal

    def negative_signals(self):
        return [s for s in self.signals if s.negative]

    def positive_rate(self):
        if not self.signals:
            return 0.0
        return 1.0 - len(self.negative_signals()) / len(self.signals)


__all__ = ["FeedbackProcessor", "FeedbackSignal"]
