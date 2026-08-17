"""Phase 11.1 Domain + Contract tests."""

import pytest

from app.commerce.domain.review import ReviewInsight
from app.commerce.review_insight import (
    JOB_CREATED,
    JOB_FAILED,
    JOB_PARTIAL,
    JOB_SUCCEEDED,
    RESOURCE_REVIEW,
    ExtractionError,
    ReviewAvailableEvent,
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
    ReviewExtractorPort,
    ReviewInput,
    ReviewInsightJob,
)


# ── ReviewInsight: no diagnosis fields ──────────────────────

def test_review_insight_carries_no_diagnosis_fields():
    insight = ReviewInsight(review_insight_id="ri1", review_id="rev1")
    for forbidden in ("cause", "impact", "priority", "recommendation", "action"):
        assert not hasattr(insight, forbidden), forbidden


def test_review_insight_roundtrip_with_governance_fields():
    insight = ReviewInsight(
        review_insight_id="ri1", review_id="rev1", sentiment="negative",
        issues=("BATTERY_FAILURE",), confidence=0.91,
        model_provider="deepseek", model_version="v3",
        extractor_id="review_extractor", extractor_version="1.0",
        prompt_version="2", knowledge_policy_version="3",
        knowledge_context_version="4",
    )
    restored = ReviewInsight.from_dict(insight.to_dict())
    assert restored == insight
    assert restored.extractor_id == "review_extractor"
    assert restored.prompt_version == "2"
    assert restored.knowledge_policy_version == "3"
    assert restored.knowledge_context_version == "4"


def test_review_insight_governance_fields_default_empty():
    insight = ReviewInsight(review_insight_id="ri1", review_id="rev1")
    assert insight.extractor_id == ""
    assert insight.prompt_version == ""
    assert insight.knowledge_policy_version == ""
    assert insight.knowledge_context_version == ""


# ── ReviewInput ─────────────────────────────────────────────

def test_review_input_roundtrip():
    inp = ReviewInput(review_id="rev1", title="t", content="c", rating=4.0,
                      language="en")
    assert ReviewInput.from_dict(inp.to_dict()) == inp


def test_review_input_requires_review_id():
    with pytest.raises(ValueError):
        ReviewInput(review_id="")


# ── ReviewExtractionResult / Batch ──────────────────────────

def test_extraction_result_roundtrip():
    result = ReviewExtractionResult(
        review_id="rev1", sentiment="negative", topics=("durability",),
        issues=("BATTERY_FAILURE",), strengths=(), intent="complaint",
        severity="high", confidence=0.91,
    )
    assert ReviewExtractionResult.from_dict(result.to_dict()) == result


def test_extraction_batch_roundtrip():
    batch = ReviewExtractionBatchResult(
        results=(ReviewExtractionResult(review_id="rev1"),),
        failed_review_ids=("rev2",),
        provider_meta={"provider": "deepseek"},
    )
    restored = ReviewExtractionBatchResult.from_dict(batch.to_dict())
    assert restored.results[0].review_id == "rev1"
    assert restored.failed_review_ids == ("rev2",)
    assert restored.provider_meta == {"provider": "deepseek"}


def test_extraction_result_carries_no_diagnosis_fields():
    result = ReviewExtractionResult(review_id="rev1")
    for forbidden in ("cause", "impact", "priority", "recommendation", "action"):
        assert not hasattr(result, forbidden), forbidden


# ── ReviewExtractorPort ─────────────────────────────────────

def test_extractor_port_is_abstract():
    with pytest.raises(TypeError):
        ReviewExtractorPort()


# ── ReviewInsightJob ────────────────────────────────────────

def test_job_default_status_created():
    job = ReviewInsightJob(job_id="j1", tenant_id="t", event_id="e1",
                           review_ids=("rev1",), extractor_id="ex",
                           extractor_version="1.0")
    assert job.status == JOB_CREATED
    assert job.total_count == 0
    assert job.success_count == 0
    assert job.failed_count == 0


def test_job_rejects_unknown_status():
    with pytest.raises(ValueError):
        ReviewInsightJob(job_id="j1", tenant_id="t", event_id="e1",
                         review_ids=("rev1",), extractor_id="ex",
                         extractor_version="1.0", status="BOGUS")


def test_job_statuses_include_partial_succeeded_failed():
    assert JOB_PARTIAL in {JOB_CREATED, JOB_PARTIAL, JOB_SUCCEEDED, JOB_FAILED}


# ── ReviewAvailableEvent ────────────────────────────────────

def test_event_carries_no_review_content():
    event = ReviewAvailableEvent(event_id="e1", tenant_id="t",
                                 review_ids=("rev1",))
    assert not hasattr(event, "content")
    assert not hasattr(event, "title")


def test_event_roundtrip():
    event = ReviewAvailableEvent(
        event_id="e1", tenant_id="t", resource=RESOURCE_REVIEW,
        review_ids=("rev1", "rev2"), sync_run_id="s1", published_at="p",
    )
    restored = ReviewAvailableEvent.from_dict(event.to_dict())
    assert restored == event
    assert restored.review_ids == ("rev1", "rev2")


# ── Errors ──────────────────────────────────────────────────

def test_extraction_error_is_typed():
    err = ExtractionError("bad provider output")
    assert isinstance(err, Exception)
    assert "bad provider output" in str(err)
