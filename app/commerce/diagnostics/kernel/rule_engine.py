"""RuleEngine — executes a versioned RuleSet against Signals and Evidence.

The engine only matches declarative antecedents and assembles a ``Cause``; it
holds no business knowledge.  Support is computed deterministically:

- base support level comes from the rule's consequent;
- a missing required Evidence code downgrades to INSUFFICIENT_EVIDENCE
  (UNKNOWN due to missing data);
- a present contradicting Evidence code downgrades one support level.

When no rule fires, a single UNKNOWN cause (INSUFFICIENT_EVIDENCE) is emitted.
"""

import uuid

from app.commerce.contracts.cause import (
    ROLE_CORRELATED,
    SUPPORT_INSUFFICIENT_EVIDENCE,
    Cause,
)
from app.commerce.contracts.signal import (
    SIGNAL_ABNORMAL,
    SIGNAL_CRITICAL,
    SIGNAL_NORMAL,
    SIGNAL_WARNING,
    Signal,
)

ALGORITHM_VERSION = "antecedent_match_v1"

_SIGNAL_STATUS_ORDER = {
    SIGNAL_NORMAL: 0,
    SIGNAL_WARNING: 1,
    SIGNAL_ABNORMAL: 2,
    SIGNAL_CRITICAL: 3,
}

_SUPPORT_ORDER = (
    SUPPORT_INSUFFICIENT_EVIDENCE,  # 0
    "POSSIBLE",                     # 1
    "SUPPORTED",                    # 2
    "STRONGLY_SUPPORTED",           # 3
    "CONFIRMED",                    # 4
)

_SUPPORT_SCORES = {
    "CONFIRMED": 1.0,
    "STRONGLY_SUPPORTED": 0.8,
    "SUPPORTED": 0.6,
    "POSSIBLE": 0.4,
    SUPPORT_INSUFFICIENT_EVIDENCE: 0.2,
}


def _downgrade(support_level):
    index = _SUPPORT_ORDER.index(support_level)
    return _SUPPORT_ORDER[max(index - 1, 0)]


def _period_overlaps(period, analysis_period):
    """Temporal alignment: an Evidence period must overlap the analysis period.

    A missing period is treated as aligned (the caller has already scoped it).
    """
    if period is None:
        return True
    if analysis_period is None:
        return True
    if (analysis_period.end is not None and period.start is not None
            and period.start > analysis_period.end):
        return False
    if (analysis_period.start is not None and period.end is not None
            and period.end < analysis_period.start):
        return False
    return True


class RuleEngine:
    ALGORITHM_VERSION = ALGORITHM_VERSION

    def evaluate(self, signals, evidence, rule_set, subject, analysis_period=None):
        """Evaluate ``rule_set`` and return the list of ``Cause`` objects.

        ``signals`` / ``evidence`` are the collected facts.  Subject alignment
        defaults to SAME_SUBJECT: only signals/evidence whose subject equals
        ``subject`` are considered, so cross-SKU/Store facts are never silently
        combined into a Cause.  ``analysis_period`` (optional) additionally
        enforces temporal alignment for Evidence.
        """
        signal_index = {}
        for signal in signals:
            if subject is not None and signal.subject != subject:
                continue
            signal_index.setdefault(signal.signal_code, []).append(signal)
        evidence_index = {}
        for item in evidence:
            if subject is not None and item.subject != subject:
                continue
            if not _period_overlaps(item.period, analysis_period):
                continue
            evidence_index.setdefault(item.code, []).append(item)

        causes = []
        for rule in rule_set.rules:
            matched_ids = self._match(rule, signal_index)
            if not matched_ids:
                continue
            causes.append(self._build_cause(rule, matched_ids, evidence_index,
                                            rule_set, subject))
        if not causes and self._has_candidate(signal_index):
            causes.append(self._unknown_cause(rule_set, subject))
        return causes

    @staticmethod
    def _has_candidate(signal_index):
        """A WARNING+ signal exists (so UNKNOWN is meaningful), else no cause."""
        return any(
            _SIGNAL_STATUS_ORDER.get(signal.status, -1) >= _SIGNAL_STATUS_ORDER[SIGNAL_WARNING]
            for signals in signal_index.values() for signal in signals
        )

    def _match(self, rule, signal_index):
        matched_ids = []
        for condition in rule.antecedents:
            candidates = signal_index.get(condition.signal_code, [])
            best = None
            for signal in candidates:
                if _SIGNAL_STATUS_ORDER.get(signal.status, -1) < _SIGNAL_STATUS_ORDER.get(
                    condition.minimum_status, 0
                ):
                    continue
                if condition.direction is not None and signal.direction != condition.direction:
                    continue
                best = signal
                break
            if best is None:
                return []
            matched_ids.append(best.signal_id)
        return matched_ids

    def _build_cause(self, rule, matched_signal_ids, evidence_index, rule_set, subject):
        consequent = rule.consequent
        support_level = consequent.support_level
        contradicting_ids = []
        for code in consequent.contradicting_evidence:
            if code in evidence_index:
                contradicting_ids.extend(item.evidence_id for item in evidence_index[code])
        supporting_ids = [
            item.evidence_id for code in consequent.required_evidence
            if code in evidence_index for item in evidence_index[code]
        ]
        missing_required = [
            code for code in consequent.required_evidence if code not in evidence_index
        ]
        if missing_required:
            support_level = SUPPORT_INSUFFICIENT_EVIDENCE
        elif contradicting_ids:
            support_level = _downgrade(support_level)

        return Cause(
            cause_id=uuid.uuid4().hex,
            cause_code=consequent.cause_code,
            domain=rule_set.domain,
            subject=subject,
            causal_role=consequent.causal_role,
            support_level=support_level,
            supporting_signal_ids=tuple(matched_signal_ids),
            supporting_evidence_ids=tuple(supporting_ids),
            contradicting_evidence_ids=tuple(contradicting_ids),
            rule_id=rule.rule_id,
            rule_version=rule.version,
            score=_SUPPORT_SCORES[support_level],
        )

    def _unknown_cause(self, rule_set, subject):
        return Cause(
            cause_id=uuid.uuid4().hex,
            cause_code=rule_set.unknown_cause_code,
            domain=rule_set.domain,
            subject=subject,
            causal_role=ROLE_CORRELATED,
            support_level=SUPPORT_INSUFFICIENT_EVIDENCE,
            rule_id="",
            rule_version="",
            score=_SUPPORT_SCORES[SUPPORT_INSUFFICIENT_EVIDENCE],
        )


__all__ = ["RuleEngine", "ALGORITHM_VERSION"]
