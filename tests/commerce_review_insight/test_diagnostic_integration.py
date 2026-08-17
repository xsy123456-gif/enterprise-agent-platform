"""Phase 11.6 Diagnostic Integration tests."""

import pytest

from app.commerce.contracts.cause import SUPPORT_INSUFFICIENT_EVIDENCE, SUPPORT_SUPPORTED
from app.commerce.contracts.evidence import EVIDENCE_AI_DERIVED
from app.commerce.contracts.signal import SIGNAL_ABNORMAL, Signal
from app.commerce.contracts.subject import SUBJECT_LISTING, SubjectRef
from app.commerce.diagnostics.definitions.rules import (
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleSet,
)
from app.commerce.diagnostics.kernel.rule_engine import RuleEngine
from app.commerce.domain import ReviewInsight
from app.commerce.review_insight.evidence_adapter import ReviewInsightEvidenceAdapter
from app.commerce.review_insight.metric_source_adapter import (
    MetricSourceAdapter,
    REVIEW_METRICS,
)

LISTING_SUBJECT = SubjectRef(SUBJECT_LISTING, "listing_1")


def _insight(issues=("BATTERY_FAILURE",)):
    return ReviewInsight(
        review_insight_id="ri1", review_id="rev1", sentiment="negative",
        issues=issues, confidence=0.91, severity="high",
        extractor_id="review_extractor", extractor_version="1.0",
        model_provider="deepseek", model_version="v3", prompt_version="2",
    )


# ── Adapter: ReviewInsight -> Evidence ──────────────────────

def test_adapter_maps_insight_to_evidence():
    adapter = ReviewInsightEvidenceAdapter()
    evidence = adapter.to_evidence(_insight(), LISTING_SUBJECT)
    assert len(evidence) == 1
    item = evidence[0]
    assert item.code == "REVIEW_BATTERY_FAILURE"
    assert item.confidence == 0.91
    assert item.evidence_type == EVIDENCE_AI_DERIVED
    assert item.subject == LISTING_SUBJECT
    assert item.provenance.adapter_id == "review_extractor"
    assert item.provenance.adapter_version == "1.0"
    assert item.definition_version == "1.0"
    assert item.algorithm_version == "v3"


def test_adapter_maps_multiple_issues():
    adapter = ReviewInsightEvidenceAdapter()
    evidence = adapter.to_evidence(
        _insight(issues=("BATTERY_FAILURE", "SHIPPING_DELAY")), LISTING_SUBJECT)
    assert {e.code for e in evidence} == {
        "REVIEW_BATTERY_FAILURE", "REVIEW_SHIPPING_DELAY"}


def test_adapter_for_listing_and_store_subjects():
    adapter = ReviewInsightEvidenceAdapter()
    listing_evidence = adapter.to_evidence_for_listing(_insight(), "listing_1")
    store_evidence = adapter.to_evidence_for_store(_insight(), "JP01")
    assert listing_evidence[0].subject.type == "LISTING"
    assert store_evidence[0].subject.type == "STORE"


def test_evidence_never_emits_business_conclusion():
    adapter = ReviewInsightEvidenceAdapter()
    evidence = adapter.to_evidence(_insight(), LISTING_SUBJECT)
    item = evidence[0]
    assert hasattr(item, "evidence_type") and not hasattr(item, "cause_code")
    for forbidden in ("cause", "impact", "priority", "recommendation", "action"):
        assert forbidden not in item.to_dict()


# ── Diagnostic Kernel consumes the Evidence ─────────────────

def _battery_rule_set():
    return RuleSet(
        rule_set_id="review_issues", version="1.0", domain="review",
        rules=(
            Rule(
                rule_id="r1", version="1.0",
                antecedents=(RuleCondition(
                    signal_code="NEGATIVE_REVIEW_SPIKE",
                    minimum_status=SIGNAL_ABNORMAL,
                ),),
                consequent=RuleConsequent(
                    cause_code="BATTERY_ISSUE",
                    required_evidence=("REVIEW_BATTERY_FAILURE",),
                ),
            ),
        ),
    )


def _spike_signal():
    return Signal(
        signal_id="s1", signal_code="NEGATIVE_REVIEW_SPIKE", domain="review",
        subject=LISTING_SUBJECT, status=SIGNAL_ABNORMAL,
    )


def test_rule_engine_consumes_review_insight_evidence():
    adapter = ReviewInsightEvidenceAdapter()
    evidence = adapter.to_evidence(_insight(), LISTING_SUBJECT)
    causes = RuleEngine().evaluate(
        signals=[_spike_signal()], evidence=evidence,
        rule_set=_battery_rule_set(), subject=LISTING_SUBJECT,
    )
    assert len(causes) == 1
    cause = causes[0]
    assert cause.cause_code == "BATTERY_ISSUE"
    assert cause.support_level == SUPPORT_SUPPORTED
    assert set(cause.supporting_evidence_ids) == {e.evidence_id for e in evidence}


def test_rule_engine_downgrades_when_evidence_missing():
    causes = RuleEngine().evaluate(
        signals=[_spike_signal()], evidence=(),
        rule_set=_battery_rule_set(), subject=LISTING_SUBJECT,
    )
    assert len(causes) == 1
    assert causes[0].cause_code == "BATTERY_ISSUE"
    assert causes[0].support_level == SUPPORT_INSUFFICIENT_EVIDENCE
    assert causes[0].supporting_evidence_ids == ()


# ── MetricSourceAdapter skeleton ────────────────────────────

def test_metric_source_adapter_declares_metrics():
    adapter = MetricSourceAdapter()
    assert adapter.available_metrics() == REVIEW_METRICS
    assert "NEGATIVE_REVIEW_RATE" in REVIEW_METRICS


def test_metric_source_adapter_computes_nothing():
    adapter = MetricSourceAdapter()
    with pytest.raises(NotImplementedError):
        adapter.map(_insight())
