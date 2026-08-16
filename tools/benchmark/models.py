"""Benchmark typed contracts (Phase 18.15).

Scenario definitions and Ground Truth are typed, physically isolated, and never
imported by the platform.  Ground Truth references the *frozen* cause / signal /
state taxonomies — it is never produced by running the production rule engine.
"""

from dataclasses import dataclass, field

# Evaluation verdicts
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_NOT_APPLICABLE = "NOT_APPLICABLE"
VERDICTS = frozenset({VERDICT_PASS, VERDICT_FAIL, VERDICT_NOT_APPLICABLE})

# Layered evaluation (E1..E5)
LAYERS = ("E1", "E2", "E3", "E4", "E5")

# Frozen diagnostic states (Signal status / Diagnostic status union used by GT)
STATE_NORMAL = "NORMAL"
STATE_WARNING = "WARNING"
STATE_ABNORMAL = "ABNORMAL"
STATE_CRITICAL = "CRITICAL"
STATE_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
STATE_UNKNOWN = "UNKNOWN"
STATE_NOT_APPLICABLE = "NOT_APPLICABLE"


def frozen_cause_codes():
    """The frozen v1 cause taxonomy (read from the versioned rule definitions —
    catalog lookup only, never a rule-engine evaluation)."""
    from app.commerce.diagnostics.definitions.business import (
        build_business_rule_sets,
    )
    codes = set()
    for rule_set in build_business_rule_sets():
        for rule in rule_set.rules:
            if rule.consequent:
                codes.add(rule.consequent.cause_code)
    return frozenset(codes)


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    category: str
    agent_id: str
    locale: str
    as_of: str
    message: str
    subject: str = ""
    setup: dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "category": self.category,
            "agent_id": self.agent_id,
            "locale": self.locale,
            "as_of": self.as_of,
            "message": self.message,
            "subject": self.subject,
            "setup": dict(self.setup or {}),
        }


@dataclass(frozen=True)
class EvaluationResult:
    layer: str
    verdict: str
    assertions: tuple = ()

    @property
    def passed(self):
        return self.verdict == VERDICT_PASS

    def to_dict(self):
        return {
            "layer": self.layer,
            "verdict": self.verdict,
            "assertions": list(self.assertions),
        }


__all__ = [
    "Scenario",
    "EvaluationResult",
    "frozen_cause_codes",
    "VERDICT_PASS",
    "VERDICT_FAIL",
    "VERDICT_NOT_APPLICABLE",
    "VERDICTS",
    "LAYERS",
    "STATE_NORMAL",
    "STATE_WARNING",
    "STATE_ABNORMAL",
    "STATE_CRITICAL",
    "STATE_INSUFFICIENT_DATA",
    "STATE_UNKNOWN",
    "STATE_NOT_APPLICABLE",
]
