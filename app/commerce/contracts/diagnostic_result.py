"""DiagnosticResult and Priority contracts.

``DiagnosticResult`` is the deterministic, structured output of a Skill run
over a DiagnosticPlan.  It must NOT contain free-form reasoning,
chain-of-thought, an uncontrolled summary, or an LLM root cause.  It carries
the full versioned provenance (applied_versions) so any result is replayable.

``Priority`` is computed by the versioned PriorityPolicy, never by an LLM.  It
distinguishes severity from priority, and records the factors that produced the
P0-P3 level.
"""

from dataclasses import dataclass, field

from app.commerce.contracts.cause import Cause
from app.commerce.contracts.errors import CommerceValidationError
from app.commerce.contracts.evidence import Evidence
from app.commerce.contracts.impact import Impact
from app.commerce.contracts.query import DataQuality, TimeRange
from app.commerce.contracts.signal import Signal
from app.commerce.contracts.subject import SubjectRef

PRIORITY_P0 = "P0"
PRIORITY_P1 = "P1"
PRIORITY_P2 = "P2"
PRIORITY_P3 = "P3"
PRIORITY_LEVELS = frozenset({PRIORITY_P0, PRIORITY_P1, PRIORITY_P2, PRIORITY_P3})

DIAG_STATUS_COMPLETED = "COMPLETED"
DIAG_STATUS_PARTIAL = "PARTIAL"
DIAG_STATUS_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
DIAG_STATUS_FAILED = "FAILED"
DIAG_STATUSES = frozenset({
    DIAG_STATUS_COMPLETED,
    DIAG_STATUS_PARTIAL,
    DIAG_STATUS_INSUFFICIENT_DATA,
    DIAG_STATUS_FAILED,
})


@dataclass(frozen=True)
class Priority:
    level: str = PRIORITY_P3
    severity: str = ""
    business_impact: str = ""
    urgency: str = ""
    confidence: float | None = None
    actionability: str = ""
    policy_id: str = ""
    policy_version: str = ""
    score: float | None = None

    def __post_init__(self):
        if self.level not in PRIORITY_LEVELS:
            raise CommerceValidationError(f"unknown priority level: {self.level}")

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "severity": self.severity,
            "business_impact": self.business_impact,
            "urgency": self.urgency,
            "confidence": self.confidence,
            "actionability": self.actionability,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "score": self.score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Priority":
        return cls(
            level=data.get("level", PRIORITY_P3),
            severity=data.get("severity", ""),
            business_impact=data.get("business_impact", ""),
            urgency=data.get("urgency", ""),
            confidence=data.get("confidence"),
            actionability=data.get("actionability", ""),
            policy_id=data.get("policy_id", ""),
            policy_version=data.get("policy_version", ""),
            score=data.get("score"),
        )


@dataclass(frozen=True)
class AppliedVersions:
    metric_definitions: dict = field(default_factory=dict)
    policies: dict = field(default_factory=dict)
    rule_sets: dict = field(default_factory=dict)
    algorithms: dict = field(default_factory=dict)
    impact_formulas: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "metric_definitions", dict(self.metric_definitions or {}))
        object.__setattr__(self, "policies", dict(self.policies or {}))
        object.__setattr__(self, "rule_sets", dict(self.rule_sets or {}))
        object.__setattr__(self, "algorithms", dict(self.algorithms or {}))
        object.__setattr__(self, "impact_formulas", dict(self.impact_formulas or {}))

    def to_dict(self) -> dict:
        return {
            "metric_definitions": dict(self.metric_definitions),
            "policies": dict(self.policies),
            "rule_sets": dict(self.rule_sets),
            "algorithms": dict(self.algorithms),
            "impact_formulas": dict(self.impact_formulas),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppliedVersions":
        return cls(
            metric_definitions=data.get("metric_definitions", {}),
            policies=data.get("policies", {}),
            rule_sets=data.get("rule_sets", {}),
            algorithms=data.get("algorithms", {}),
            impact_formulas=data.get("impact_formulas", {}),
        )


@dataclass(frozen=True)
class DiagnosticResult:
    diagnostic_id: str
    skill_id: str
    skill_version: str
    plan_id: str
    plan_version: str
    subject: SubjectRef
    analysis_period: TimeRange
    status: str = DIAG_STATUS_COMPLETED
    scenario_id: str | None = None
    comparison_period: TimeRange | None = None
    evidence: tuple[Evidence, ...] = ()
    signals: tuple[Signal, ...] = ()
    causes: tuple[Cause, ...] = ()
    impacts: tuple[Impact, ...] = ()
    priority: Priority = field(default_factory=Priority)
    data_quality: DataQuality = field(default_factory=DataQuality)
    coverage: float = 0.0
    unavailable_evidence: tuple[str, ...] = ()
    applied_versions: AppliedVersions = field(default_factory=AppliedVersions)
    trace_id: str = ""
    execution_id: str = ""
    generated_at: str = ""

    def __post_init__(self):
        object.__setattr__(self, "evidence", tuple(self.evidence or ()))
        object.__setattr__(self, "signals", tuple(self.signals or ()))
        object.__setattr__(self, "causes", tuple(self.causes or ()))
        object.__setattr__(self, "impacts", tuple(self.impacts or ()))
        object.__setattr__(self, "unavailable_evidence", tuple(self.unavailable_evidence or ()))
        if self.status not in DIAG_STATUSES:
            raise CommerceValidationError(f"unknown diagnostic status: {self.status}")

    def to_dict(self) -> dict:
        return {
            "diagnostic_id": self.diagnostic_id,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "subject": self.subject.to_dict(),
            "analysis_period": self.analysis_period.to_dict(),
            "status": self.status,
            "scenario_id": self.scenario_id,
            "comparison_period": self.comparison_period.to_dict() if self.comparison_period else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "signals": [s.to_dict() for s in self.signals],
            "causes": [c.to_dict() for c in self.causes],
            "impacts": [i.to_dict() for i in self.impacts],
            "priority": self.priority.to_dict(),
            "data_quality": self.data_quality.to_dict(),
            "coverage": self.coverage,
            "unavailable_evidence": list(self.unavailable_evidence),
            "applied_versions": self.applied_versions.to_dict(),
            "trace_id": self.trace_id,
            "execution_id": self.execution_id,
            "generated_at": self.generated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiagnosticResult":
        return cls(
            diagnostic_id=data["diagnostic_id"],
            skill_id=data["skill_id"],
            skill_version=data["skill_version"],
            plan_id=data["plan_id"],
            plan_version=data["plan_version"],
            subject=SubjectRef.from_dict(data["subject"]),
            analysis_period=TimeRange.from_dict(data["analysis_period"]),
            status=data.get("status", DIAG_STATUS_COMPLETED),
            scenario_id=data.get("scenario_id"),
            comparison_period=TimeRange.from_dict(data["comparison_period"]) if data.get("comparison_period") else None,
            evidence=tuple(Evidence.from_dict(e) for e in data.get("evidence", ())),
            signals=tuple(Signal.from_dict(s) for s in data.get("signals", ())),
            causes=tuple(Cause.from_dict(c) for c in data.get("causes", ())),
            impacts=tuple(Impact.from_dict(i) for i in data.get("impacts", ())),
            priority=Priority.from_dict(data["priority"]) if data.get("priority") else Priority(),
            data_quality=DataQuality.from_dict(data["data_quality"]) if data.get("data_quality") else DataQuality(),
            coverage=data.get("coverage", 0.0),
            unavailable_evidence=tuple(data.get("unavailable_evidence", ())),
            applied_versions=AppliedVersions.from_dict(data["applied_versions"]) if data.get("applied_versions") else AppliedVersions(),
            trace_id=data.get("trace_id", ""),
            execution_id=data.get("execution_id", ""),
            generated_at=data.get("generated_at", ""),
        )


__all__ = [
    "Priority",
    "AppliedVersions",
    "DiagnosticResult",
    "PRIORITY_LEVELS",
    "PRIORITY_P0",
    "PRIORITY_P1",
    "PRIORITY_P2",
    "PRIORITY_P3",
    "DIAG_STATUSES",
    "DIAG_STATUS_COMPLETED",
    "DIAG_STATUS_PARTIAL",
    "DIAG_STATUS_INSUFFICIENT_DATA",
    "DIAG_STATUS_FAILED",
]
