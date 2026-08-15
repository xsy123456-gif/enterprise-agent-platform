"""PlanIR — the compiled, version-pinned, immutable plan form.

Every referenced definition (metric / policy / rule set / impact formula /
priority policy) is pinned to an explicit version here, so replay never drifts
with the active version.  The checksum is a deterministic SHA-256 over the
canonical serialization of the IR (excluding runtime fields).
"""

import hashlib
import json
from dataclasses import dataclass, field

REF_METRIC = "metric"
REF_POLICY = "policy"
REF_RULE_SET = "ruleset"
REF_IMPACT_FORMULA = "impact_formula"
REF_PRIORITY_POLICY = "priority_policy"
REF_KINDS = frozenset({
    REF_METRIC, REF_POLICY, REF_RULE_SET, REF_IMPACT_FORMULA, REF_PRIORITY_POLICY,
})


@dataclass(frozen=True)
class PinnedRef:
    kind: str
    id: str
    version: str

    def to_dict(self) -> dict:
        return {"kind": self.kind, "id": self.id, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict) -> "PinnedRef":
        return cls(kind=data["kind"], id=data["id"], version=data["version"])


@dataclass(frozen=True)
class CompiledStep:
    step_id: str
    type: str
    params: dict = field(default_factory=dict)
    when: tuple = ()
    on_failure: str = "SKIP"
    next: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "params", dict(self.params or {}))
        object.__setattr__(self, "when", tuple(self.when or ()))
        object.__setattr__(self, "next", tuple(self.next or ()))

    def to_dict(self) -> dict:
        return {
            "step_id": self.step_id,
            "type": self.type,
            "params": _plain(self.params),
            "when": [w.to_dict() for w in self.when],
            "on_failure": self.on_failure,
            "next": list(self.next),
        }


@dataclass(frozen=True)
class PlanIR:
    plan_id: str
    version: str
    domain: str
    skill_id: str = ""
    skill_version: str = ""
    steps: tuple[CompiledStep, ...] = ()
    dependencies: tuple[PinnedRef, ...] = ()
    required_evidence: tuple[str, ...] = ()
    optional_evidence: tuple[str, ...] = ()
    max_depth: int = 3
    analysis_period: dict | None = None
    comparison_period: dict | None = None
    checksum: str = ""
    compiled_at: str = ""

    def __post_init__(self):
        object.__setattr__(self, "steps", tuple(self.steps or ()))
        object.__setattr__(self, "dependencies", tuple(self.dependencies or ()))
        object.__setattr__(self, "required_evidence", tuple(self.required_evidence or ()))
        object.__setattr__(self, "optional_evidence", tuple(self.optional_evidence or ()))

    def canonical_payload(self) -> dict:
        """Deterministic, order-independent IR payload (excluding checksum)."""
        return {
            "plan_id": self.plan_id,
            "version": self.version,
            "domain": self.domain,
            "skill_id": self.skill_id,
            "skill_version": self.skill_version,
            "steps": [s.to_dict() for s in self.steps],
            "dependencies": sorted((d.to_dict() for d in self.dependencies),
                                   key=lambda d: (d["kind"], d["id"], d["version"])),
            "required_evidence": sorted(self.required_evidence),
            "optional_evidence": sorted(self.optional_evidence),
            "max_depth": self.max_depth,
            "analysis_period": self.analysis_period,
            "comparison_period": self.comparison_period,
        }

    def compute_checksum(self) -> str:
        serialized = json.dumps(
            _canonical(self.canonical_payload()), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _canonical(value):
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    return value


def _plain(value):
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, PinnedRef):
        return value.to_dict()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


__all__ = [
    "PinnedRef",
    "CompiledStep",
    "PlanIR",
    "REF_METRIC",
    "REF_POLICY",
    "REF_RULE_SET",
    "REF_IMPACT_FORMULA",
    "REF_PRIORITY_POLICY",
    "REF_KINDS",
]
