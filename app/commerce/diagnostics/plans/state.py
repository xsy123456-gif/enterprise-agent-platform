"""PlanExecutionState — the mutable runtime state of one plan execution."""

from dataclasses import dataclass, field

from app.commerce.contracts.subject import SubjectRef
from app.commerce.diagnostics.plans.schema import (
    STEP_STATUS_PENDING,
    STOP_SUCCESS,
)


@dataclass
class StepTrace:
    step_id: str
    type: str
    status: str
    error: str = ""


@dataclass
class PlanExecutionState:
    plan_id: str
    plan_version: str
    checksum: str
    execution_id: str
    subject: SubjectRef

    # step outputs
    evidence: list = field(default_factory=list)
    metric_results: dict = field(default_factory=dict)
    data_quality: object = None
    signals: list = field(default_factory=list)
    contributions: object = None
    causes: list = field(default_factory=list)
    impacts: list = field(default_factory=list)
    priority: object = None
    diagnostic_result: object = None

    # control
    step_statuses: dict = field(default_factory=dict)
    coverage: float = 1.0
    unavailable_evidence: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    trace: list = field(default_factory=list)
    outcome: str = STOP_SUCCESS
    _terminated: bool = field(default=False, repr=False)

    # ── controlled state accessors (used by WHEN) ────────────

    def signal_status(self, code):
        for signal in self.signals:
            if signal.signal_code == code:
                return signal.status
        return None

    def signal_direction(self, code):
        for signal in self.signals:
            if signal.signal_code == code:
                return signal.direction
        return None

    def evidence_quality(self, code):
        for evidence in self.evidence:
            if evidence.code == code:
                return evidence.quality
        return None

    def has_signal(self, code):
        return self.signal_status(code) is not None

    def has_evidence(self, code):
        return any(e.code == code for e in self.evidence)

    def has_cause(self, code):
        return any(c.cause_code == code for c in self.causes)

    def evidence_value(self, code):
        for evidence in self.evidence:
            if evidence.code == code:
                return evidence.value
        return None

    def metric_value(self, name):
        result = self.metric_results.get(name)
        return result.value if result is not None else None

    # ── control helpers ──────────────────────────────────────

    def mark(self, step_id, status, error=""):
        self.step_statuses[step_id] = status
        self.trace.append(StepTrace(step_id=step_id, type="", status=status, error=error))

    def missing_required(self, required_codes):
        return [code for code in required_codes if not self.has_evidence(code)]


__all__ = ["PlanExecutionState", "StepTrace", "STEP_STATUS_PENDING"]
