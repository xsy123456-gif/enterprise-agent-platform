"""Optimization generator (Phase 17.2).

Turns a detected issue into an ``OptimizationProposal``.  An optional LLM may
suggest the *candidate change text* only — it never modifies any component
directly.
"""

import uuid

from app.platform.intelligence.optimization.analyzer import (
    ISSUE_COST,
    ISSUE_FEEDBACK,
    ISSUE_PERFORMANCE,
    ISSUE_QUALITY,
    DetectedIssue,
)
from app.platform.intelligence.optimization.proposal import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    TARGET_PLAN,
    TARGET_PROMPT,
    TARGET_SKILL,
    OptimizationProposal,
)

_ISSUE_TARGET = {
    ISSUE_PERFORMANCE: TARGET_SKILL,
    ISSUE_COST: TARGET_PROMPT,
    ISSUE_QUALITY: TARGET_PLAN,
    ISSUE_FEEDBACK: TARGET_PROMPT,
}


class OptimizationGenerator:

    def __init__(self, llm=None):
        self.llm = llm

    def generate(self, issue: DetectedIssue, target_id: str,
                 current_version: str = "1.0") -> OptimizationProposal:
        target_type = _ISSUE_TARGET.get(issue.issue_type, TARGET_PLAN)
        risk = self._risk(issue)
        suggested = self._suggested_change(issue, target_type, target_id)
        return OptimizationProposal(
            proposal_id=uuid.uuid4().hex,
            target_type=target_type, target_id=target_id,
            current_version=current_version, suggested_change=suggested,
            reason=issue.message, evidence=issue.evidence, risk_level=risk,
        )

    def _risk(self, issue: DetectedIssue) -> str:
        if issue.issue_type == ISSUE_PERFORMANCE:
            failure_rate = issue.evidence.get("failure_rate", 0.0)
            if failure_rate > 0.3:
                return RISK_HIGH
            return RISK_MEDIUM
        if issue.issue_type == ISSUE_COST:
            return RISK_LOW
        if issue.issue_type == ISSUE_FEEDBACK:
            return RISK_MEDIUM
        return RISK_MEDIUM

    def _suggested_change(self, issue, target_type, target_id):
        base = f"优化 {target_type} {target_id}：{issue.message}"
        if self.llm is not None:
            candidate = self.llm(base)
            if isinstance(candidate, str) and candidate.strip():
                return candidate
        return base


__all__ = ["OptimizationGenerator"]
