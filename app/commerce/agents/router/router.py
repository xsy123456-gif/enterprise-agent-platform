"""Skill router pipeline (Phase 12.3).

Pipeline: Rule (Layer 1) -> Entity (Layer 2, enriches subject) -> LLM (Layer 3).
A selected skill is always validated against the agent's available skill set;
the LLM can never select a skill outside it nor inject tool/permission/plan.
"""

from app.commerce.agents.router.contract import (
    SkillRoutingRequest,
    SkillRoutingResult,
)


class SkillRouter:

    def __init__(self, rule_router=None, entity_router=None, llm_router=None):
        self.rule_router = rule_router
        self.entity_router = entity_router
        self.llm_router = llm_router

    def route(self, request: SkillRoutingRequest) -> SkillRoutingResult:
        available = tuple(request.available_skills)
        subject = self._extract_subject(request)

        if self.rule_router is not None:
            hit = self.rule_router.route(request)
            if hit is not None and hit[0] in available:
                skill_id, confidence = hit
                return SkillRoutingResult(
                    selected_skill=skill_id, confidence=confidence,
                    alternatives=self._alternatives(skill_id, available),
                    reason="rule-keyword-match", layer="rule", subject=subject,
                )

        if self.llm_router is not None:
            hit = self.llm_router.route(request)
            if hit is not None and hit[0] in available:
                skill_id, confidence = hit
                return SkillRoutingResult(
                    selected_skill=skill_id, confidence=confidence,
                    alternatives=self._alternatives(skill_id, available),
                    reason="llm-intent", layer="llm", subject=subject,
                )

        return SkillRoutingResult(subject=subject, reason="no-match")

    def _extract_subject(self, request):
        if self.entity_router is None:
            return None
        matches = self.entity_router.extract(request.message)
        return matches[0].subject if matches else None

    @staticmethod
    def _alternatives(selected, available):
        return tuple(s for s in available if s != selected)


__all__ = ["SkillRouter"]
