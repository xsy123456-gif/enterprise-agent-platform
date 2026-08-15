"""RuleEngine tests: declarative rule matching, support/evidence model, UNKNOWN."""

import pytest

from app.commerce.contracts.cause import (
    ROLE_CONTRIBUTING,
    ROLE_PRIMARY,
    SUPPORT_CONFIRMED,
    SUPPORT_INSUFFICIENT_EVIDENCE,
    SUPPORT_POSSIBLE,
)
from app.commerce.contracts.evidence import Evidence
from app.commerce.contracts.signal import (
    SIGNAL_ABNORMAL,
    SIGNAL_CRITICAL,
    SIGNAL_INSUFFICIENT_DATA,
    SIGNAL_NOT_APPLICABLE,
    SIGNAL_UNKNOWN,
    Signal,
)
from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics import (
    Rule,
    RuleCondition,
    RuleConsequent,
    RuleEngine,
    RuleSet,
)

SUBJECT = SubjectRef("STORE", "store_amazon_001")
OTHER_SUBJECT = SubjectRef("SKU", "sku_000087")


def _signal(signal_id, code, status=SIGNAL_ABNORMAL, direction="DOWN"):
    return Signal(
        signal_id=signal_id, signal_code=code, domain="sales", subject=SUBJECT,
        status=status, direction=direction,
    )


def _evidence(code, evidence_id=None):
    return Evidence(
        evidence_id=evidence_id or f"ev_{code}", subject=SUBJECT,
        evidence_type="METRIC", code=code,
    )


def _rule(rule_id, antecedents, consequent):
    return Rule(rule_id=rule_id, version="1.0", antecedents=tuple(antecedents),
                consequent=consequent)


def _ruleset(rules):
    return RuleSet(rule_set_id="commerce.conversion.v1", version="1.0",
                   domain="conversion", rules=tuple(rules))


def test_primary_cause_inferred():
    rules = [
        _rule(
            "r1",
            [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN"),
             RuleCondition("NEGATIVE_REVIEW_RATE_RISE", "WARNING")],
            RuleConsequent(
                cause_code="PRODUCT_REPUTATION_DETERIORATION",
                causal_role=ROLE_PRIMARY, support_level=SUPPORT_CONFIRMED,
                required_evidence=("REVIEW_RATING",),
            ),
        )
    ]
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP"), _signal("s2", "NEGATIVE_REVIEW_RATE_RISE")],
        evidence=[_evidence("REVIEW_RATING")],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert len(causes) == 1
    assert causes[0].cause_code == "PRODUCT_REPUTATION_DETERIORATION"
    assert causes[0].causal_role == ROLE_PRIMARY
    assert causes[0].support_level == SUPPORT_CONFIRMED
    assert causes[0].score == 1.0


def test_missing_required_evidence_downgrades():
    rules = [
        _rule(
            "r1",
            [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
            RuleConsequent(
                cause_code="PRODUCT_REPUTATION_DETERIORATION",
                causal_role=ROLE_PRIMARY, support_level=SUPPORT_CONFIRMED,
                required_evidence=("REVIEW_RATING",),
            ),
        )
    ]
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP")],
        evidence=[],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert causes[0].support_level == SUPPORT_INSUFFICIENT_EVIDENCE
    assert causes[0].cause_code == "PRODUCT_REPUTATION_DETERIORATION"


def test_contradicting_evidence_downgrades():
    rules = [
        _rule(
            "r1",
            [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
            RuleConsequent(
                cause_code="PRODUCT_REPUTATION_DETERIORATION",
                causal_role=ROLE_PRIMARY, support_level=SUPPORT_CONFIRMED,
                contradicting_evidence=("PRICE_INCREASE",),
            ),
        )
    ]
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP")],
        evidence=[_evidence("PRICE_INCREASE")],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    # CONFIRMED downgraded one level -> STRONGLY_SUPPORTED.
    assert causes[0].support_level == "STRONGLY_SUPPORTED"
    assert causes[0].contradicting_evidence_ids == ("ev_PRICE_INCREASE",)


def test_no_rule_fires_emits_unknown():
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "SOME_OTHER_SIGNAL")],
        evidence=[],
        rule_set=_ruleset([
            _rule("r1", [RuleCondition("CVR_DROP", "ABNORMAL")],
                  RuleConsequent("PRODUCT_REPUTATION_DETERIORATION")),
        ]),
        subject=SUBJECT,
    )
    assert len(causes) == 1
    assert causes[0].cause_code == "UNKNOWN"
    assert causes[0].support_level == SUPPORT_INSUFFICIENT_EVIDENCE


def test_status_threshold_and_direction():
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "CRITICAL", "DOWN")],
              RuleConsequent("SEVERE_CONVERSION_ISSUE", ROLE_PRIMARY, SUPPORT_CONFIRMED))
    ]
    engine = RuleEngine()
    # ABNORMAL is below CRITICAL -> no match -> UNKNOWN.
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP", SIGNAL_ABNORMAL, "DOWN")],
        evidence=[], rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert causes[0].cause_code == "UNKNOWN"
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP", SIGNAL_CRITICAL, "DOWN")],
        evidence=[], rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert causes[0].cause_code == "SEVERE_CONVERSION_ISSUE"


def test_multiple_causes():
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "ABNORMAL")],
              RuleConsequent("PRODUCT_REPUTATION_DETERIORATION", ROLE_PRIMARY, "SUPPORTED")),
        _rule("r2", [RuleCondition("CVR_DROP", "ABNORMAL")],
              RuleConsequent("PRICE_INCREASE", ROLE_CONTRIBUTING, SUPPORT_POSSIBLE)),
    ]
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP")], evidence=[],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert {c.cause_code for c in causes} == {
        "PRODUCT_REPUTATION_DETERIORATION", "PRICE_INCREASE"
    }


def test_supporting_evidence_and_signal_ids_recorded():
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "ABNORMAL")],
              RuleConsequent("PRODUCT_REPUTATION_DETERIORATION", ROLE_PRIMARY,
                             SUPPORT_CONFIRMED, required_evidence=("REVIEW_RATING",)))
    ]
    engine = RuleEngine()
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP")],
        evidence=[_evidence("REVIEW_RATING")],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert causes[0].supporting_signal_ids == ("s1",)
    assert causes[0].supporting_evidence_ids == ("ev_REVIEW_RATING",)
    assert causes[0].rule_id == "r1"
    assert causes[0].rule_version == "1.0"


def test_cross_subject_evidence_not_combined():
    # Evidence for a different SKU must not support a Store-level cause.
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "ABNORMAL")],
              RuleConsequent("PRODUCT_REPUTATION_DETERIORATION", ROLE_PRIMARY,
                             SUPPORT_CONFIRMED, required_evidence=("REVIEW_RATING",)))
    ]
    engine = RuleEngine()
    cross_subject_evidence = Evidence(
        evidence_id="ev_other", subject=OTHER_SUBJECT, evidence_type="METRIC",
        code="REVIEW_RATING",
    )
    causes = engine.evaluate(
        signals=[_signal("s1", "CVR_DROP")],
        evidence=[cross_subject_evidence],
        rule_set=_ruleset(rules), subject=SUBJECT,
    )
    # Required evidence not present for THIS subject -> downgraded.
    assert causes[0].support_level == SUPPORT_INSUFFICIENT_EVIDENCE
    assert causes[0].supporting_evidence_ids == ()


def test_cross_subject_signal_not_combined():
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "ABNORMAL", "DOWN")],
              RuleConsequent("X", ROLE_PRIMARY, SUPPORT_CONFIRMED))
    ]
    engine = RuleEngine()
    # The only CVR_DROP signal is for a different SKU -> no match -> UNKNOWN.
    causes = engine.evaluate(
        signals=[Signal(signal_id="s_other", signal_code="CVR_DROP", domain="conversion",
                        subject=OTHER_SUBJECT, status=SIGNAL_ABNORMAL, direction="DOWN")],
        evidence=[], rule_set=_ruleset(rules), subject=SUBJECT,
    )
    assert causes[0].cause_code == "UNKNOWN"


def test_minimum_status_rejects_non_severity_values():
    with pytest.raises(ValueError):
        RuleCondition("CVR_DROP", SIGNAL_INSUFFICIENT_DATA)
    with pytest.raises(ValueError):
        RuleCondition("CVR_DROP", SIGNAL_UNKNOWN)
    with pytest.raises(ValueError):
        RuleCondition("CVR_DROP", SIGNAL_NOT_APPLICABLE)


def test_non_severity_signal_never_satisfies_threshold():
    rules = [
        _rule("r1", [RuleCondition("CVR_DROP", "WARNING")],
              RuleConsequent("X", ROLE_PRIMARY, SUPPORT_CONFIRMED))
    ]
    engine = RuleEngine()
    # INSUFFICIENT_DATA / UNKNOWN / NOT_APPLICABLE can never satisfy a threshold.
    for status in (SIGNAL_INSUFFICIENT_DATA, SIGNAL_UNKNOWN, SIGNAL_NOT_APPLICABLE):
        causes = engine.evaluate(
            signals=[_signal("s1", "CVR_DROP", status)],
            evidence=[], rule_set=_ruleset(rules), subject=SUBJECT,
        )
        assert causes[0].cause_code == "UNKNOWN"
