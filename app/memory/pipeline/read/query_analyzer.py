import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class QueryAnalysis:
    semantic_required: bool
    keywords: list[str] = field(default_factory=list)


class MemoryQueryAnalyzer:
    """Deterministic routing between exact SQL and semantic retrieval."""

    SEMANTIC_CUES = (
        "为什么", "如何", "原因", "建议", "相似", "关系", "影响",
        "why", "how", "reason", "similar", "relationship",
    )

    def analyze(self, query):
        text = query.strip()
        keywords = re.findall(r"[A-Za-z0-9_-]+|[\u4e00-\u9fff]{2,}", text)
        has_exact_identifier = bool(
            re.search(r"\d{4,}|[A-Za-z]{2,}[-_]\d+", text)
        )
        has_semantic_cue = any(cue in text.lower() for cue in self.SEMANTIC_CUES)
        return QueryAnalysis(
            semantic_required=has_semantic_cue or not has_exact_identifier,
            keywords=keywords,
        )
