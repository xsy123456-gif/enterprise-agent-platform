"""Phase 12.7 Response Layer tests."""

from types import SimpleNamespace

from app.commerce.agents.response import ResponseBuilder
from app.commerce.contracts.cause import Cause
from app.commerce.contracts.diagnostic_result import DiagnosticResult, Priority
from app.commerce.contracts.query import TimeRange
from app.commerce.contracts.signal import SIGNAL_ABNORMAL, Signal
from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef

SUBJECT = SubjectRef(SUBJECT_STORE, "JP01")


def _diagnostic():
    return DiagnosticResult(
        diagnostic_id="d1", skill_id="store_performance_diagnosis",
        skill_version="1.0", plan_id="store_health_scan", plan_version="1.0",
        subject=SUBJECT,
        analysis_period=TimeRange(start="2026-08-01", end="2026-08-08"),
        signals=(Signal(signal_id="s1", signal_code="GMV_DROP", domain="sales",
                        subject=SUBJECT, status=SIGNAL_ABNORMAL),),
        causes=(Cause(cause_id="c1", cause_code="GMV_DECLINE", domain="sales",
                      subject=SUBJECT),),
        priority=Priority(level="P1"),
    )


def test_builder_base_message_deterministic():
    builder = ResponseBuilder()
    first = builder.build(_diagnostic())
    second = builder.build(_diagnostic())
    assert first.message == second.message
    assert "STORE:JP01" in first.message
    assert "GMV_DROP" in first.message
    assert "GMV_DECLINE" in first.message
    assert "P1" in first.message


def test_builder_preserves_structured_result():
    builder = ResponseBuilder()
    diagnostic = _diagnostic()
    response = builder.build(diagnostic)
    assert response.diagnostic_result is diagnostic
    assert response.evidence == diagnostic.evidence


def test_builder_llm_polishes_message_only():
    def llm(base, diagnostic):
        return f"【润色】{base}"
    builder = ResponseBuilder(llm=llm)
    diagnostic = _diagnostic()
    response = builder.build(diagnostic)
    assert response.message.startswith("【润色】")
    assert response.diagnostic_result is diagnostic
    assert response.diagnostic_result.causes == diagnostic.causes


def test_builder_llm_cannot_rejudge_cause():
    def malicious_llm(base, diagnostic):
        return "真正原因是供应商断货，不是销量问题"
    builder = ResponseBuilder(llm=malicious_llm)
    diagnostic = _diagnostic()
    response = builder.build(diagnostic)
    # LLM text lands in message, but the structured cause is untouched.
    assert response.diagnostic_result.causes == diagnostic.causes
    assert response.diagnostic_result.causes[0].cause_code == "GMV_DECLINE"


def test_builder_llm_failure_falls_back():
    def broken_llm(base, diagnostic):
        raise RuntimeError("llm down")
    builder = ResponseBuilder(llm=broken_llm)
    diagnostic = _diagnostic()
    response = builder.build(diagnostic)
    assert "GMV_DECLINE" in response.message
