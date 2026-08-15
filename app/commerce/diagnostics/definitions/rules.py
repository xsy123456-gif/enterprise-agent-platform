"""Rule / RuleSet definition and IR.

Rules are declarative and versioned — no Python code, no eval, no LLM.  A rule
states: when these signal antecedents hold, assert this cause (with a causal
role and base support level).  ``required_evidence`` / ``contradicting_evidence``
name Evidence codes that raise or lower support, enabling UNKNOWN /
INSUFFICIENT_EVIDENCE handling.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuleCondition:
    """An antecedent: a signal must exist with status >= ``minimum_status``
    (and, optionally, the given direction)."""

    signal_code: str
    minimum_status: str = "ABNORMAL"
    direction: str | None = None

    def to_dict(self) -> dict:
        return {
            "signal_code": self.signal_code,
            "minimum_status": self.minimum_status,
            "direction": self.direction,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleCondition":
        return cls(
            signal_code=data["signal_code"],
            minimum_status=data.get("minimum_status", "ABNORMAL"),
            direction=data.get("direction"),
        )


@dataclass(frozen=True)
class RuleConsequent:
    """The asserted cause when all antecedents hold."""

    cause_code: str
    causal_role: str = "CONTRIBUTING"
    support_level: str = "SUPPORTED"
    required_evidence: tuple[str, ...] = ()
    contradicting_evidence: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence or ()))
        object.__setattr__(
            self, "contradicting_evidence", tuple(self.contradicting_evidence or ())
        )

    def to_dict(self) -> dict:
        return {
            "cause_code": self.cause_code,
            "causal_role": self.causal_role,
            "support_level": self.support_level,
            "required_evidence": list(self.required_evidence),
            "contradicting_evidence": list(self.contradicting_evidence),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleConsequent":
        return cls(
            cause_code=data["cause_code"],
            causal_role=data.get("causal_role", "CONTRIBUTING"),
            support_level=data.get("support_level", "SUPPORTED"),
            required_evidence=tuple(data.get("required_evidence", ())),
            contradicting_evidence=tuple(data.get("contradicting_evidence", ())),
        )


@dataclass(frozen=True)
class Rule:
    rule_id: str
    version: str
    name: str = ""
    antecedents: tuple[RuleCondition, ...] = ()
    consequent: RuleConsequent | None = None

    def __post_init__(self):
        object.__setattr__(self, "antecedents", tuple(self.antecedents or ()))

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "version": self.version,
            "name": self.name,
            "antecedents": [a.to_dict() for a in self.antecedents],
            "consequent": self.consequent.to_dict() if self.consequent else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Rule":
        return cls(
            rule_id=data["rule_id"],
            version=data["version"],
            name=data.get("name", ""),
            antecedents=tuple(RuleCondition.from_dict(a) for a in data.get("antecedents", ())),
            consequent=RuleConsequent.from_dict(data["consequent"]) if data.get("consequent") else None,
        )


@dataclass(frozen=True)
class RuleSet:
    rule_set_id: str
    version: str
    domain: str = ""
    rules: tuple[Rule, ...] = ()
    unknown_cause_code: str = "UNKNOWN"

    def __post_init__(self):
        object.__setattr__(self, "rules", tuple(self.rules or ()))

    def to_dict(self) -> dict:
        return {
            "rule_set_id": self.rule_set_id,
            "version": self.version,
            "domain": self.domain,
            "rules": [r.to_dict() for r in self.rules],
            "unknown_cause_code": self.unknown_cause_code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RuleSet":
        return cls(
            rule_set_id=data["rule_set_id"],
            version=data["version"],
            domain=data.get("domain", ""),
            rules=tuple(Rule.from_dict(r) for r in data.get("rules", ())),
            unknown_cause_code=data.get("unknown_cause_code", "UNKNOWN"),
        )


__all__ = ["RuleCondition", "RuleConsequent", "Rule", "RuleSet"]
