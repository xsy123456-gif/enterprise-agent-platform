"""Phase 17.5 Feedback Intelligence tests."""

import pytest

from app.platform.intelligence.feedback import AgentFeedback, FeedbackProcessor


def test_negative_feedback_produces_optimization_signal():
    processor = FeedbackProcessor()
    signal = processor.process(AgentFeedback(
        feedback_id="f1", execution_id="e1", user_id="u1", rating=1.0,
        category="WRONG_DIAGNOSIS", correction="应该是库存问题"))
    assert signal.negative is True
    assert signal.message == "应该是库存问题"


def test_positive_feedback_signal():
    processor = FeedbackProcessor()
    signal = processor.process(AgentFeedback(
        feedback_id="f1", execution_id="e1", user_id="u1", rating=5.0,
        category="GOOD_RESULT"))
    assert signal.negative is False


def test_positive_rate():
    processor = FeedbackProcessor()
    processor.process(AgentFeedback(feedback_id="f1", category="GOOD_RESULT"))
    processor.process(AgentFeedback(feedback_id="f2", category="GOOD_RESULT"))
    processor.process(AgentFeedback(feedback_id="f3", category="TOO_EXPENSIVE"))
    assert processor.positive_rate() == pytest.approx(2 / 3)
