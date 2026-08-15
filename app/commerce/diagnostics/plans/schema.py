"""Declarative DiagnosticPlan schema.

A plan is a finite DAG of typed steps.  Step definitions are declarative data —
no Python code, no SQL, no eval/exec, no prompt/LLM.  ``when`` conditions
consume only controlled structured state.
"""

from dataclasses import dataclass, field

STEP_FACT_QUERY = "FACT_QUERY"
STEP_METRIC_COMPUTE = "METRIC_COMPUTE"
STEP_DATA_QUALITY_GATE = "DATA_QUALITY_GATE"
STEP_ANOMALY_DETECT = "ANOMALY_DETECT"
STEP_CONTRIBUTION_ANALYZE = "CONTRIBUTION_ANALYZE"
STEP_RULE_EVALUATE = "RULE_EVALUATE"
STEP_IMPACT_ESTIMATE = "IMPACT_ESTIMATE"
STEP_PRIORITY_EVALUATE = "PRIORITY_EVALUATE"
STEP_RESULT_ASSEMBLE = "RESULT_ASSEMBLE"

STEP_TYPES = frozenset({
    STEP_FACT_QUERY,
    STEP_METRIC_COMPUTE,
    STEP_DATA_QUALITY_GATE,
    STEP_ANOMALY_DETECT,
    STEP_CONTRIBUTION_ANALYZE,
    STEP_RULE_EVALUATE,
    STEP_IMPACT_ESTIMATE,
    STEP_PRIORITY_EVALUATE,
    STEP_RESULT_ASSEMBLE,
})

STOP_SUCCESS = "STOP_SUCCESS"
STOP_NORMAL = "STOP_NORMAL"
STOP_INSUFFICIENT_DATA = "STOP_INSUFFICIENT_DATA"
STOP_UNSUPPORTED = "STOP_UNSUPPORTED"
STOP_OUTCOMES = frozenset({
    STOP_SUCCESS, STOP_NORMAL, STOP_INSUFFICIENT_DATA, STOP_UNSUPPORTED,
})

FAILURE_SKIP = "SKIP"
FAILURE_MARK_UNKNOWN = "MARK_UNKNOWN"
FAILURE_STOP = "STOP"
FAILURE_POLICIES = frozenset({FAILURE_SKIP, FAILURE_MARK_UNKNOWN, FAILURE_STOP})

# Plan lifecycle states (§55)
PLAN_DRAFT = "DRAFT"
PLAN_VALIDATED = "VALIDATED"
PLAN_ACTIVE = "ACTIVE"
PLAN_DEPRECATED = "DEPRECATED"
PLAN_DISABLED = "DISABLED"
PLAN_STATUSES = frozenset({
    PLAN_DRAFT, PLAN_VALIDATED, PLAN_ACTIVE, PLAN_DEPRECATED, PLAN_DISABLED,
})

# Step execution statuses.
STEP_STATUS_PENDING = "PENDING"
STEP_STATUS_SUCCEEDED = "SUCCEEDED"
STEP_STATUS_SKIPPED = "SKIPPED"
STEP_STATUS_FAILED = "FAILED"
STEP_STATUS_MARKED_UNKNOWN = "MARKED_UNKNOWN"


@dataclass(frozen=True)
class WhenCondition:
    """A gate on controlled structured state.

    ``path`` must be a whitelisted state path (see ``plans.when``); ``operator``
    is a small fixed set.  No arbitrary expression is allowed.
    """

    path: str
    operator: str
    value: object = None

    def to_dict(self) -> dict:
        return {"path": self.path, "operator": self.operator, "value": self.value}

    @classmethod
    def from_dict(cls, data: dict) -> "WhenCondition":
        return cls(
            path=data["path"], operator=data["operator"], value=data.get("value"),
        )


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    type: str
    params: dict = field(default_factory=dict)
    when: tuple[WhenCondition, ...] = ()
    on_failure: str = FAILURE_SKIP
    next: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "params", dict(self.params or {}))
        object.__setattr__(self, "when", tuple(self.when or ()))
        object.__setattr__(self, "next", tuple(self.next or ()))

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "type": self.type,
            "params": dict(self.params),
            "when": [w.to_dict() for w in self.when],
            "on_failure": self.on_failure,
            "next": list(self.next),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StepDefinition":
        return cls(
            step_id=data["step_id"],
            type=data["type"],
            params=data.get("params", {}),
            when=tuple(WhenCondition.from_dict(w) for w in data.get("when", ())),
            on_failure=data.get("on_failure", FAILURE_SKIP),
            next=tuple(data.get("next", ())),
        )


@dataclass(frozen=True)
class PlanDefinition:
    plan_id: str
    version: str
    domain: str
    skill_id: str = ""
    skill_version: str = ""
    steps: tuple[StepDefinition, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    required_evidence: tuple[str, ...] = ()
    optional_evidence: tuple[str, ...] = ()
    max_depth: int = 3
    # Period *specification* (e.g. {"days": 7}), not a resolved runtime TimeRange.
    analysis_period: dict | None = None
    comparison_period: dict | None = None

    def __post_init__(self):
        object.__setattr__(self, "steps", tuple(self.steps or ()))
        object.__setattr__(self, "required_capabilities", tuple(self.required_capabilities or ()))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence or ()))
        object.__setattr__(self, "optional_evidence", tuple(self.optional_evidence or ()))

    def step_ids(self):
        return {step.step_id for step in self.steps}

    def step(self, step_id):
        for step in self.steps:
            if step.step_id == step_id:
                return step
        return None

    def entry_step_id(self):
        return self.steps[0].step_id if self.steps else ""

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "domain": self.domain,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "steps": [s.to_dict() for s in self.steps],
            "required_capabilities": list(self.required_capabilities),
            "required_evidence": list(self.required_evidence),
            "optional_evidence": list(self.optional_evidence),
            "max_depth": self.max_depth,
            "analysis_period": self.analysis_period,
            "comparison_period": self.comparison_period,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PlanDefinition":
        return cls(
            plan_id=data["plan_id"],
            version=data["version"],
            domain=data["domain"],
            skill_id=data.get("skill_id", ""),
            skill_version=data.get("skill_version", ""),
            steps=tuple(StepDefinition.from_dict(s) for s in data.get("steps", ())),
            required_capabilities=tuple(data.get("required_capabilities", ())),
            required_evidence=tuple(data.get("required_evidence", ())),
            optional_evidence=tuple(data.get("optional_evidence", ())),
            max_depth=data.get("max_depth", 3),
            analysis_period=data.get("analysis_period"),
            comparison_period=data.get("comparison_period"),
        )


@dataclass(frozen=True)
class DataQualityRequirement:
    """Typed quality gate policy.  The handler applies it verbatim — no
    thresholds are hard-coded in the handler."""

    requirement_id: str = ""
    version: str = ""
    required_evidence_codes: tuple[str, ...] = ()
    min_coverage: float = 1.0
    unacceptable_evidence_qualities: tuple[str, ...] = ("STALE", "MISSING", "INVALID")
    unacceptable_metric_statuses: tuple[str, ...] = ("INSUFFICIENT", "NULL_RESULT")
    unacceptable_freshness: tuple[str, ...] = ("STALE",)

    def __post_init__(self):
        object.__setattr__(self, "required_evidence_codes", tuple(self.required_evidence_codes or ()))
        object.__setattr__(self, "unacceptable_evidence_qualities", tuple(self.unacceptable_evidence_qualities or ()))
        object.__setattr__(self, "unacceptable_metric_statuses", tuple(self.unacceptable_metric_statuses or ()))
        object.__setattr__(self, "unacceptable_freshness", tuple(self.unacceptable_freshness or ()))

    @classmethod
    def from_dict(cls, data: dict) -> "DataQualityRequirement":
        if data is None:
            return cls()
        return cls(
            requirement_id=data.get("requirement_id", ""),
            version=data.get("version", ""),
            required_evidence_codes=tuple(data.get("required_evidence_codes", ())),
            min_coverage=data.get("min_coverage", 1.0),
            unacceptable_evidence_qualities=tuple(data.get("unacceptable_evidence_qualities", ("STALE", "MISSING", "INVALID"))),
            unacceptable_metric_statuses=tuple(data.get("unacceptable_metric_statuses", ("INSUFFICIENT", "NULL_RESULT"))),
            unacceptable_freshness=tuple(data.get("unacceptable_freshness", ("STALE",))),
        )


__all__ = [
    "WhenCondition",
    "StepDefinition",
    "PlanDefinition",
    "DataQualityRequirement",
    "STEP_TYPES",
    "STEP_FACT_QUERY",
    "STEP_METRIC_COMPUTE",
    "STEP_DATA_QUALITY_GATE",
    "STEP_ANOMALY_DETECT",
    "STEP_CONTRIBUTION_ANALYZE",
    "STEP_RULE_EVALUATE",
    "STEP_IMPACT_ESTIMATE",
    "STEP_PRIORITY_EVALUATE",
    "STEP_RESULT_ASSEMBLE",
    "STOP_OUTCOMES",
    "STOP_SUCCESS",
    "STOP_NORMAL",
    "STOP_INSUFFICIENT_DATA",
    "STOP_UNSUPPORTED",
    "FAILURE_POLICIES",
    "FAILURE_SKIP",
    "FAILURE_MARK_UNKNOWN",
    "FAILURE_STOP",
    "PLAN_STATUSES",
    "PLAN_DRAFT",
    "PLAN_VALIDATED",
    "PLAN_ACTIVE",
    "PLAN_DEPRECATED",
    "PLAN_DISABLED",
    "STEP_STATUS_PENDING",
    "STEP_STATUS_SUCCEEDED",
    "STEP_STATUS_SKIPPED",
    "STEP_STATUS_FAILED",
    "STEP_STATUS_MARKED_UNKNOWN",
]
