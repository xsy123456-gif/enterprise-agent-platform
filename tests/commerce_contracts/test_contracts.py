"""Commerce contract tests: validation (fail-closed) and serialization."""

import pytest

from app.commerce.contracts import (
    Cause,
    CommerceValidationError,
    DataProvenance,
    DataQuality,
    DiagnosticResult,
    Evidence,
    Filter,
    FreshnessMetadata,
    Impact,
    PageInfo,
    PageRequest,
    Priority,
    QueryResult,
    Signal,
    SubjectRef,
    TimeRange,
    ToolError,
    OperationalIssue,
)
from app.commerce.contracts.cause import ROLE_PRIMARY, SUPPORT_CONFIRMED
from app.commerce.contracts.diagnostic_result import PRIORITY_P1
from app.commerce.contracts.evidence import (
    EVIDENCE_METRIC,
    EVIDENCE_QUALITY_VALID,
)
from app.commerce.contracts.errors import INVALID_REQUEST, RATE_LIMITED
from app.commerce.contracts.signal import (
    DIRECTION_DOWN,
    SIGNAL_ABNORMAL,
)
from app.commerce.domain import Store


# --- SubjectRef ---

def test_subject_ref_roundtrip():
    ref = SubjectRef(type="STORE", id="store_amazon_001")
    assert SubjectRef.from_dict(ref.to_dict()) == ref
    assert ref.key() == "STORE:store_amazon_001"


def test_subject_ref_rejects_unknown_type():
    with pytest.raises(CommerceValidationError):
        SubjectRef(type="WAREHOUSE", id="x")


def test_subject_ref_rejects_empty_id():
    with pytest.raises(CommerceValidationError):
        SubjectRef(type="STORE", id="")


# --- Filter ---

def test_filter_validation():
    assert Filter(field="status", operator="EQ", value="active")
    assert Filter(field="price", operator="RANGE", value=(1.0, 10.0))


def test_filter_rejects_unknown_operator():
    with pytest.raises(CommerceValidationError):
        Filter(field="price", operator="LIKE", value="x")


def test_filter_rejects_bad_range():
    with pytest.raises(CommerceValidationError):
        Filter(field="price", operator="RANGE", value=5.0)


# --- TimeRange / PageRequest ---

def test_time_range_rejects_inverted():
    with pytest.raises(CommerceValidationError):
        TimeRange(start="2026-08-10", end="2026-08-01")


def test_page_request_rejects_nonpositive_limit():
    with pytest.raises(CommerceValidationError):
        PageRequest(limit=0)


# --- Freshness / Quality / Provenance ---

def test_freshness_rejects_unknown_status():
    with pytest.raises(CommerceValidationError):
        FreshnessMetadata(status="HOT")


def test_data_quality_rejects_unknown_status():
    with pytest.raises(CommerceValidationError):
        DataQuality(status="MAYBE")


def test_provenance_rejects_unknown_source_type():
    with pytest.raises(CommerceValidationError):
        DataProvenance(source_type="RAW_DB")


# --- Evidence ---

def test_evidence_roundtrip():
    subject = SubjectRef(type="STORE", id="store_amazon_001")
    ev = Evidence(
        evidence_id="e1", subject=subject, evidence_type=EVIDENCE_METRIC,
        code="GMV", value=1000.0, unit="USD", quality=EVIDENCE_QUALITY_VALID,
    )
    assert Evidence.from_dict(ev.to_dict()) == ev


def test_evidence_rejects_unknown_type():
    with pytest.raises(CommerceValidationError):
        Evidence(
            evidence_id="e1", subject=SubjectRef("STORE", "s"),
            evidence_type="MAGIC", code="GMV",
        )


# --- Signal ---

def test_signal_roundtrip():
    sig = Signal(
        signal_id="s1", signal_code="GMV_DROP", domain="sales",
        subject=SubjectRef("STORE", "s"), status=SIGNAL_ABNORMAL,
        direction=DIRECTION_DOWN,
    )
    assert Signal.from_dict(sig.to_dict()) == sig


def test_signal_rejects_unknown_status():
    with pytest.raises(CommerceValidationError):
        Signal(
            signal_id="s1", signal_code="X", domain="sales",
            subject=SubjectRef("STORE", "s"), status="MEH",
        )


def test_signal_rejects_unknown_direction():
    with pytest.raises(CommerceValidationError):
        Signal(
            signal_id="s1", signal_code="X", domain="sales",
            subject=SubjectRef("STORE", "s"), direction="SIDEWAYS",
        )


# --- Cause ---

def test_cause_roundtrip():
    cause = Cause(
        cause_id="c1", cause_code="TRAFFIC_DECLINE", domain="sales",
        subject=SubjectRef("STORE", "s"), causal_role=ROLE_PRIMARY,
        support_level=SUPPORT_CONFIRMED,
    )
    assert Cause.from_dict(cause.to_dict()) == cause


def test_cause_rejects_unknown_role():
    with pytest.raises(CommerceValidationError):
        Cause(
            cause_id="c1", cause_code="X", domain="sales",
            subject=SubjectRef("STORE", "s"), causal_role="SOMETIMES",
        )


# --- Impact ---

def test_impact_roundtrip():
    impact = Impact(
        impact_id="i1", impact_type="ESTIMATED",
        classification="REVENUE_LOSS", value=500.0, unit="USD",
    )
    assert Impact.from_dict(impact.to_dict()) == impact


def test_impact_rejects_unknown_type():
    with pytest.raises(CommerceValidationError):
        Impact(impact_id="i1", impact_type="GUESSED", classification="X", value=1.0)


# --- Priority ---

def test_priority_roundtrip():
    p = Priority(level=PRIORITY_P1, score=0.85)
    assert Priority.from_dict(p.to_dict()) == p


def test_priority_rejects_unknown_level():
    with pytest.raises(CommerceValidationError):
        Priority(level="P9")


# --- DiagnosticResult ---

def test_diagnostic_result_roundtrip():
    subject = SubjectRef("STORE", "s")
    ev = Evidence(
        evidence_id="e1", subject=subject, evidence_type=EVIDENCE_METRIC, code="GMV",
    )
    result = DiagnosticResult(
        diagnostic_id="d1", skill_id="store_performance_diagnosis",
        skill_version="1.0", plan_id="gmv_decline_diagnosis", plan_version="1.0",
        subject=subject, analysis_period=TimeRange(start="2026-08-01", end="2026-08-07"),
        evidence=(ev,), priority=Priority(level=PRIORITY_P1),
    )
    restored = DiagnosticResult.from_dict(result.to_dict())
    assert restored == result
    assert restored.evidence[0].code == "GMV"
    assert restored.priority.level == PRIORITY_P1


# --- QueryResult ---

def test_query_result_roundtrip_with_domain_items():
    store = Store(
        store_id="store_amazon_001", tenant_id="company_A", platform="amazon",
        marketplace="US", external_store_id="ext", name="Amazon001",
        currency="USD", timezone="UTC",
    )
    result = QueryResult(
        request_id="q1", data=(store,),
        page=PageInfo(returned_count=1),
    )
    dumped = result.to_dict()
    assert dumped["data"][0]["store_id"] == "store_amazon_001"


# --- ToolError ---

def test_tool_error_from_code():
    err = ToolError.from_code(RATE_LIMITED, trace_id="t1")
    assert err.code == RATE_LIMITED
    assert err.category == "UPSTREAM"
    assert err.retryable is True
    assert ToolError.from_dict(err.to_dict()) == err


def test_tool_error_invalid_request_not_retryable():
    err = ToolError.from_code(INVALID_REQUEST)
    assert err.category == "REQUEST"
    assert err.retryable is False


def test_tool_error_rejects_unknown_code():
    with pytest.raises(CommerceValidationError):
        ToolError(code="WHATEVER", category="DATA", retryable=False, message_key="x")


# --- OperationalIssue contract re-export ---

def test_operational_issue_contract_is_domain_entity():
    issue = OperationalIssue(
        issue_id="i1", tenant_id="t", store_id="s", domain="sales",
        subject_type="STORE", subject_id="s", issue_type="GMV_DECLINE",
    )
    assert issue.tenant_id == "t"
