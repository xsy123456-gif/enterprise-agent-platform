"""Phase 12.3 Router tests."""

import pytest

from app.commerce.agents.router import (
    EntityRouter,
    LLMRouter,
    RuleRouter,
    SkillRouter,
    SkillRoutingRequest,
)
from app.commerce.contracts.subject import SUBJECT_STORE, SubjectRef

SKILLS = ("store_performance_diagnosis", "advertising_performance_diagnosis",
          "inventory_risk_diagnosis")


def _request(message, available=SKILLS):
    return SkillRoutingRequest(message=message, available_skills=available)


# ── Rule router ─────────────────────────────────────────────

def test_rule_router_keyword_match():
    router = RuleRouter(keyword_map={
        "advertising_performance_diagnosis": ("广告", "ROAS", "ACOS"),
        "inventory_risk_diagnosis": ("库存", "缺货", "滞销"),
    })
    request = _request("广告花费上涨，ROAS下降")
    assert router.route(request) == ("advertising_performance_diagnosis", 0.7)


def test_rule_router_no_match():
    router = RuleRouter(keyword_map={"advertising_performance_diagnosis": ("广告",)})
    assert router.route(_request("随便聊聊")) is None


# ── Entity router ───────────────────────────────────────────

def test_entity_router_extracts_subject():
    router = EntityRouter(known_subjects={"JP01": SubjectRef(SUBJECT_STORE, "JP01")})
    matches = router.extract("帮我看看JP01为什么销量下降")
    assert matches[0].subject == SubjectRef(SUBJECT_STORE, "JP01")


def test_entity_router_no_match():
    router = EntityRouter(known_subjects={"JP01": SubjectRef(SUBJECT_STORE, "JP01")})
    assert router.extract("看看整体情况") == []


# ── LLM router ──────────────────────────────────────────────

def test_llm_router_selects_from_available():
    def llm(message, available):
        return {"candidates": ["store_performance_diagnosis"]}
    router = LLMRouter(llm=llm)
    result = router.route(_request("这个店最近不太正常"))
    assert result == ("store_performance_diagnosis", 0.6)


def test_llm_router_rejects_out_of_set():
    def llm(message, available):
        return {"candidates": ["not_a_skill"]}
    router = LLMRouter(llm=llm)
    assert router.route(_request("随便")) is None


def test_llm_router_rejects_forbidden_keys():
    def llm(message, available):
        return {"candidates": ["store_performance_diagnosis"],
                "tool": "metric.query"}
    router = LLMRouter(llm=llm)
    assert router.route(_request("随便")) is None


def test_llm_router_rejects_plan_injection():
    def llm(message, available):
        return {"candidates": ["store_performance_diagnosis"], "plan": "hack"}
    router = LLMRouter(llm=llm)
    assert router.route(_request("随便")) is None


def test_llm_router_accepts_bare_list():
    def llm(message, available):
        return ["store_performance_diagnosis"]
    router = LLMRouter(llm=llm)
    assert router.route(_request("随便")) == ("store_performance_diagnosis", 0.6)


# ── SkillRouter pipeline ────────────────────────────────────

def test_router_prefers_rule_over_llm():
    rule = RuleRouter(keyword_map={"advertising_performance_diagnosis": ("广告",)})
    def llm(message, available):
        return {"candidates": ["store_performance_diagnosis"]}
    router = SkillRouter(rule_router=rule, llm_router=LLMRouter(llm=llm))
    result = router.route(_request("广告花费上涨"))
    assert result.selected_skill == "advertising_performance_diagnosis"
    assert result.layer == "rule"


def test_router_falls_back_to_llm():
    rule = RuleRouter(keyword_map={})
    def llm(message, available):
        return {"candidates": ["store_performance_diagnosis"]}
    router = SkillRouter(rule_router=rule, llm_router=LLMRouter(llm=llm))
    result = router.route(_request("这个店感觉不太正常"))
    assert result.selected_skill == "store_performance_diagnosis"
    assert result.layer == "llm"


def test_router_attaches_entity_subject():
    rule = RuleRouter(keyword_map={"store_performance_diagnosis": ("销量", "下降")})
    entity = EntityRouter(known_subjects={"JP01": SubjectRef(SUBJECT_STORE, "JP01")})
    router = SkillRouter(rule_router=rule, entity_router=entity)
    result = router.route(_request("JP01最近销量下降原因？"))
    assert result.selected_skill == "store_performance_diagnosis"
    assert result.subject == SubjectRef(SUBJECT_STORE, "JP01")


def test_router_no_match():
    router = SkillRouter(rule_router=RuleRouter(keyword_map={}))
    result = router.route(_request("随便"))
    assert result.selected_skill == ""
    assert result.reason == "no-match"
