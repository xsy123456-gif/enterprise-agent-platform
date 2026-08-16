"""Multi-agent router (Phase 13.5).

Routes a user message to one of several agents (Commerce / Sales / Finance).
Three layers: Rule (keywords) -> Domain (department) -> LLM (complex NL).  The
LLM may only output a candidate agent id from the available set — never a tool /
permission / database / plan.
"""

import json
from dataclasses import dataclass, field

FORBIDDEN_AGENT_KEYS = (
    "tool", "tools", "permission", "permissions", "plan", "database", "scope",
)


@dataclass(frozen=True)
class AgentRoutingRequest:
    message: str
    available_agents: tuple[str, ...] = ()
    context: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "available_agents", tuple(self.available_agents or ()))
        object.__setattr__(self, "context", dict(self.context or {}))


@dataclass(frozen=True)
class AgentRoutingResult:
    selected_agent: str = ""
    confidence: float = 0.0
    alternatives: tuple[str, ...] = ()
    reason: str = ""
    layer: str = ""

    def __post_init__(self):
        object.__setattr__(self, "alternatives", tuple(self.alternatives or ()))


class RuleRouter:

    def __init__(self, keyword_map=None):
        self.keyword_map = dict(keyword_map or {})

    def route(self, request):
        message = (request.message or "").lower()
        best, best_hits = None, 0
        for agent_id, keywords in self.keyword_map.items():
            hits = sum(1 for kw in keywords if kw.lower() in message)
            if hits > best_hits:
                best, best_hits = agent_id, hits
        if best is None:
            return None
        return best, min(0.95, 0.5 + 0.1 * best_hits)


class DomainRouter:

    def __init__(self, domain_map=None):
        self.domain_map = dict(domain_map or {})

    def route(self, request):
        message = (request.message or "").lower()
        for agent_id, domains in self.domain_map.items():
            if any(d.lower() in message for d in domains):
                return agent_id, 0.8
        return None


class LLMRouter:

    def __init__(self, llm):
        self.llm = llm

    def route(self, request):
        if self.llm is None:
            return None
        raw = self.llm(request.message, list(request.available_agents))
        candidates = self._parse(raw, request.available_agents)
        if not candidates:
            return None
        return candidates[0], 0.6

    def _parse(self, raw, available_agents):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return []
        if isinstance(raw, dict):
            if any(k in raw for k in FORBIDDEN_AGENT_KEYS):
                return []
            candidates = raw.get("candidates", raw.get("candidate", []))
        elif isinstance(raw, (list, tuple)):
            candidates = raw
        else:
            return []
        if isinstance(candidates, str):
            candidates = [candidates]
        if not isinstance(candidates, (list, tuple)):
            return []
        available = set(available_agents)
        return [c for c in candidates if c in available]


class EnterpriseAgentRouter:

    def __init__(self, rule_router=None, domain_router=None, llm_router=None):
        self.rule_router = rule_router
        self.domain_router = domain_router
        self.llm_router = llm_router

    def route(self, request: AgentRoutingRequest) -> AgentRoutingResult:
        available = tuple(request.available_agents)
        if self.rule_router is not None:
            hit = self.rule_router.route(request)
            if hit and hit[0] in available:
                return self._result(hit[0], hit[1], available, "rule", "rule-keyword")
        if self.domain_router is not None:
            hit = self.domain_router.route(request)
            if hit and hit[0] in available:
                return self._result(hit[0], hit[1], available, "domain", "domain-match")
        if self.llm_router is not None:
            hit = self.llm_router.route(request)
            if hit and hit[0] in available:
                return self._result(hit[0], hit[1], available, "llm", "llm-intent")
        return AgentRoutingResult(reason="no-match")

    @staticmethod
    def _result(selected, confidence, available, layer, reason):
        return AgentRoutingResult(
            selected_agent=selected, confidence=confidence,
            alternatives=tuple(a for a in available if a != selected),
            reason=reason, layer=layer,
        )


__all__ = [
    "AgentRoutingRequest",
    "AgentRoutingResult",
    "RuleRouter",
    "DomainRouter",
    "LLMRouter",
    "EnterpriseAgentRouter",
    "FORBIDDEN_AGENT_KEYS",
]
