"""Layer 3 LLM Router (Phase 12.3).

Only handles complex natural language.  The LLM may output ONLY candidate skill
names (from the available set) — never a tool / permission / database / plan /
scope.  Any forbidden key in the LLM output voids the whole result.
"""

import json

FORBIDDEN_OUTPUT_KEYS = (
    "tool", "tools", "permission", "permissions",
    "plan", "database", "scope", "sql", "query",
)


class LLMRouter:

    def __init__(self, llm):
        self.llm = llm

    def route(self, request):
        if self.llm is None:
            return None
        raw = self.llm(request.message, list(request.available_skills))
        candidates = self._parse(raw, request.available_skills)
        if not candidates:
            return None
        return candidates[0], 0.6

    def _parse(self, raw, available_skills):
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                return []
        if isinstance(raw, dict):
            if any(key in raw for key in FORBIDDEN_OUTPUT_KEYS):
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
        available = set(available_skills)
        return [candidate for candidate in candidates if candidate in available]


__all__ = ["LLMRouter", "FORBIDDEN_OUTPUT_KEYS"]
