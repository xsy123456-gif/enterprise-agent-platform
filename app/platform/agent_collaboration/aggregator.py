"""Result aggregation + conflict resolution (Phase 14.5).

Multiple agent results are merged into one ``AggregatedAgentResult``.  When two
agents conflict on the same topic, the ``ConflictResolver`` picks deterministically
by evidence priority — Diagnostic Evidence > Agent Opinion > LLM Summary.  The
LLM never picks the winner.
"""

from dataclasses import dataclass, field

EVIDENCE_DIAGNOSTIC = "diagnostic_evidence"
EVIDENCE_AGENT_OPINION = "agent_opinion"
EVIDENCE_LLM_SUMMARY = "llm_summary"
EVIDENCE_PRIORITY = {
    EVIDENCE_DIAGNOSTIC: 3,
    EVIDENCE_AGENT_OPINION: 2,
    EVIDENCE_LLM_SUMMARY: 1,
}


@dataclass(frozen=True)
class AgentResultItem:
    agent_id: str
    summary: str = ""
    result_reference: str = ""
    confidence: float = 0.0
    evidence_type: str = EVIDENCE_AGENT_OPINION
    topic: str = "general"

    def __post_init__(self):
        if self.evidence_type not in EVIDENCE_PRIORITY:
            raise ValueError(f"unknown evidence_type: {self.evidence_type}")


@dataclass(frozen=True)
class Conflict:
    topic: str
    resolved: str
    alternatives: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "alternatives", tuple(self.alternatives or ()))


@dataclass(frozen=True)
class AggregatedAgentResult:
    task_id: str
    summary: str = ""
    agent_results: tuple = ()
    confidence: float = 0.0
    conflicts: tuple = ()

    def __post_init__(self):
        object.__setattr__(self, "agent_results", tuple(self.agent_results or ()))
        object.__setattr__(self, "conflicts", tuple(self.conflicts or ()))

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "summary": self.summary,
            "agent_results": [
                {"agent_id": i.agent_id, "summary": i.summary}
                for i in self.agent_results
            ],
            "confidence": self.confidence,
            "conflicts": [
                {"topic": c.topic, "resolved": c.resolved,
                 "alternatives": list(c.alternatives)}
                for c in self.conflicts
            ],
        }


class ConflictResolver:

    def resolve(self, items):
        if not items:
            return None
        return max(items, key=lambda i: EVIDENCE_PRIORITY.get(i.evidence_type, 0))


class AgentResultAggregator:

    def __init__(self, conflict_resolver=None):
        self.conflict_resolver = conflict_resolver or ConflictResolver()

    def aggregate(self, task_id, items) -> AggregatedAgentResult:
        groups = {}
        for item in items:
            groups.setdefault(item.topic, []).append(item)
        resolved_items = []
        conflicts = []
        for topic, group in groups.items():
            distinct = {item.summary for item in group if item.summary}
            if len(distinct) > 1:
                winner = self.conflict_resolver.resolve(group)
                alternatives = tuple(
                    sorted(distinct - {winner.summary})
                )
                conflicts.append(Conflict(
                    topic=topic, resolved=winner.summary,
                    alternatives=alternatives))
                resolved_items.append(winner)
            else:
                resolved_items.extend(group)
        summary = "；".join(i.summary for i in resolved_items if i.summary)
        confidence = min(
            (i.confidence for i in resolved_items if i.confidence > 0), default=0.0,
        )
        return AggregatedAgentResult(
            task_id=task_id, summary=summary,
            agent_results=tuple(resolved_items), confidence=confidence,
            conflicts=tuple(conflicts),
        )


__all__ = [
    "AgentResultItem",
    "AggregatedAgentResult",
    "Conflict",
    "ConflictResolver",
    "AgentResultAggregator",
    "EVIDENCE_DIAGNOSTIC",
    "EVIDENCE_AGENT_OPINION",
    "EVIDENCE_LLM_SUMMARY",
    "EVIDENCE_PRIORITY",
]
