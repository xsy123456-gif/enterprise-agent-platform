"""Phase 11.4 Extractor Provider tests."""

import json

import pytest

from app.commerce.review_insight.domain import (
    ReviewExtractionResult,
    ReviewInput,
)
from app.commerce.review_insight.errors import (
    ExtractionError,
    ExtractorUnavailableError,
)
from app.commerce.review_insight.extractor import (
    ClaudeAdapter,
    DeepSeekAdapter,
    OpenAIAdapter,
    ProviderConfig,
    ProviderExtractor,
    RuleBasedExtractor,
    build_extractor,
)
from app.commerce.domain.review import ReviewInsight


def _input(review_id="rev1", title="", content="", rating=3.0):
    return ReviewInput(
        review_id=review_id, title=title, content=content, rating=rating)


# ── Rule-based determinism ──────────────────────────────────

def test_rule_based_determinism():
    extractor = RuleBasedExtractor()
    review = _input(content="battery died after a week", rating=2.0)
    first = extractor.extract_batch([review]).results[0]
    second = extractor.extract_batch([review]).results[0]
    assert first == second
    assert first.to_dict() == second.to_dict()


def test_rule_based_negative_review():
    extractor = RuleBasedExtractor()
    result = extractor.extract_batch([
        _input(content="battery died, so disappointed", rating=2.0)]).results[0]
    assert result.sentiment == "negative"
    assert "BATTERY_FAILURE" in result.issues
    assert result.severity == "high"
    assert result.intent == "complaint"


def test_rule_based_positive_review():
    extractor = RuleBasedExtractor()
    result = extractor.extract_batch([
        _input(content="great build quality, very fast", rating=5.0)]).results[0]
    assert result.sentiment == "positive"
    assert "BUILD_QUALITY" in result.strengths
    assert result.intent == "praise"


def test_rule_based_question_intent():
    extractor = RuleBasedExtractor()
    result = extractor.extract_batch([
        _input(content="does this support fast charging?", rating=4.0)]).results[0]
    assert result.intent == "question"


def test_rule_based_no_llm_fields():
    extractor = RuleBasedExtractor()
    result = extractor.extract_batch([_input()]).results[0]
    assert isinstance(result, ReviewExtractionResult)
    assert not isinstance(result, ReviewInsight)
    assert not hasattr(result, "cause")
    assert not hasattr(result, "impact")
    assert not hasattr(result, "priority")


# ── Provider mapping (valid) ────────────────────────────────

def _deepseek_envelope(payload):
    return {"choices": [{"message": {"content": json.dumps(payload)}}]}


def _claude_envelope(payload):
    return {"content": [{"type": "text", "text": json.dumps(payload)}]}


def test_deepseek_maps_valid_response():
    adapter = DeepSeekAdapter()
    result = adapter.map_response(_deepseek_envelope({
        "review_id": "rev1", "sentiment": "negative",
        "issues": ["BATTERY_FAILURE"], "topics": ["battery"],
        "confidence": 0.92,
    }), "rev1")
    assert isinstance(result, ReviewExtractionResult)
    assert result.review_id == "rev1"
    assert result.sentiment == "negative"
    assert result.issues == ("BATTERY_FAILURE",)
    assert result.confidence == 0.92


def test_openai_maps_valid_response():
    adapter = OpenAIAdapter()
    result = adapter.map_response(_deepseek_envelope({
        "sentiment": "positive", "strengths": ["BUILD_QUALITY"],
    }), "rev2")
    assert result.review_id == "rev2"
    assert result.sentiment == "positive"
    assert result.strengths == ("BUILD_QUALITY",)


def test_claude_maps_valid_response():
    adapter = ClaudeAdapter()
    result = adapter.map_response(_claude_envelope({
        "sentiment": "neutral", "confidence": 0.5,
    }), "rev3")
    assert result.review_id == "rev3"
    assert result.sentiment == "neutral"


# ── Provider mapping: invalid output -> typed error ─────────

def test_deepseek_malformed_envelope_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response({"not": "choices"}, "rev1")


def test_deepseek_invalid_json_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(
            {"choices": [{"message": {"content": "not json"}}]}, "rev1")


def test_deepseek_non_object_json_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(
            {"choices": [{"message": {"content": "[1, 2, 3]"}}]}, "rev1")


def test_deepseek_confidence_out_of_range_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(_deepseek_envelope({"confidence": 1.7}), "rev1")


def test_deepseek_non_numeric_confidence_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(_deepseek_envelope({"confidence": "high"}), "rev1")


def test_deepseek_review_id_mismatch_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(_deepseek_envelope({"review_id": "rev9"}), "rev1")


def test_deepseek_non_string_list_item_raises():
    adapter = DeepSeekAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response(_deepseek_envelope({"issues": [1, 2]}), "rev1")


def test_claude_malformed_envelope_raises():
    adapter = ClaudeAdapter()
    with pytest.raises(ExtractionError):
        adapter.map_response({"content": "oops"}, "rev1")


# ── Provider never fabricates cause / impact / priority ─────

def test_provider_drops_forbidden_fields():
    adapter = DeepSeekAdapter()
    result = adapter.map_response(_deepseek_envelope({
        "review_id": "rev1", "sentiment": "negative",
        "cause": "battery", "impact": "high", "priority": 1,
        "recommendation": "replace", "action": "refund",
    }), "rev1")
    assert isinstance(result, ReviewExtractionResult)
    for forbidden in ("cause", "impact", "priority", "recommendation", "action"):
        assert forbidden not in result.to_dict()


def test_provider_returns_extraction_result_not_insight():
    adapter = DeepSeekAdapter()
    result = adapter.map_response(_deepseek_envelope({"sentiment": "negative"}), "rev1")
    assert isinstance(result, ReviewExtractionResult)
    assert not isinstance(result, ReviewInsight)


# ── Factory ─────────────────────────────────────────────────

def test_build_extractor_default_rule_based():
    assert isinstance(build_extractor(None), RuleBasedExtractor)
    assert isinstance(build_extractor("rule_based"), RuleBasedExtractor)
    assert isinstance(build_extractor(ProviderConfig(provider="rule_based")), RuleBasedExtractor)


def test_build_extractor_provider_without_client_raises():
    extractor = build_extractor("deepseek")
    assert isinstance(extractor, ProviderExtractor)
    assert extractor.provider_name == "deepseek"
    with pytest.raises(ExtractorUnavailableError):
        extractor.extract_batch([_input()])


def test_build_extractor_unknown_provider_raises():
    with pytest.raises(ExtractionError):
        build_extractor("nope")


# ── ProviderExtractor composition (fake client) ─────────────

class _FakeClient:
    def __init__(self, responses=None, unavailable=False):
        self.responses = responses or {}
        self.unavailable = unavailable

    def complete(self, provider_name, review, context=None):
        if self.unavailable:
            raise ExtractorUnavailableError("provider down")
        return self.responses[review.review_id]


def test_provider_extractor_maps_batch():
    client = _FakeClient({
        "rev1": _deepseek_envelope({"sentiment": "negative"}),
        "rev2": _deepseek_envelope({"sentiment": "positive"}),
    })
    extractor = ProviderExtractor(DeepSeekAdapter(), client=client)
    batch = extractor.extract_batch([_input("rev1"), _input("rev2")])
    assert len(batch.results) == 2
    assert batch.failed_review_ids == ()
    assert {r.sentiment for r in batch.results} == {"negative", "positive"}


def test_provider_extractor_partial_failure():
    client = _FakeClient({
        "rev1": _deepseek_envelope({"sentiment": "negative"}),
        "rev2": _deepseek_envelope({"confidence": 3.0}),
    })
    extractor = ProviderExtractor(DeepSeekAdapter(), client=client)
    batch = extractor.extract_batch([_input("rev1"), _input("rev2")])
    assert len(batch.results) == 1
    assert batch.failed_review_ids == ("rev2",)


def test_provider_extractor_outage_propagates():
    extractor = ProviderExtractor(DeepSeekAdapter(), client=_FakeClient(unavailable=True))
    with pytest.raises(ExtractorUnavailableError):
        extractor.extract_batch([_input("rev1")])
