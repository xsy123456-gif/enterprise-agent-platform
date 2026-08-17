"""Layer 1 Rule Router (Phase 12.3).

Highest priority: deterministic keyword matching against per-skill keywords
(derived from ``AgentSkillBinding.routing_examples``).  Never calls an LLM.
"""


class RuleRouter:

    def __init__(self, keyword_map=None):
        self.keyword_map = dict(keyword_map or {})

    def route(self, request):
        message = (request.message or "").lower()
        best = None
        best_hits = 0
        for skill_id, keywords in self.keyword_map.items():
            hits = sum(1 for keyword in keywords if keyword.lower() in message)
            if hits > best_hits:
                best = skill_id
                best_hits = hits
        if best is None:
            return None
        return best, min(0.95, 0.5 + 0.1 * best_hits)


def keyword_map_from_bindings(bindings):
    """Build {skill_id: keywords} from bindings' routing_examples."""
    mapping = {}
    for binding in bindings:
        if binding.routing_examples:
            mapping.setdefault(binding.skill_id, []).extend(binding.routing_examples)
    return {skill_id: tuple(keywords) for skill_id, keywords in mapping.items()}


__all__ = ["RuleRouter", "keyword_map_from_bindings"]
