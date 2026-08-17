"""Phase 13.5 Multi Agent Router tests."""

from app.platform.agent_control.router import (
    AgentRoutingRequest,
    DomainRouter,
    EnterpriseAgentRouter,
    LLMRouter,
    RuleRouter,
)

AGENTS = ("commerce_agent", "sales_agent", "finance_agent")


def _request(message, available=AGENTS):
    return AgentRoutingRequest(message=message, available_agents=available)


def test_rule_router_advertising_to_commerce():
    router = RuleRouter(keyword_map={
        "commerce_agent": ("广告", "ROAS", "库存", "商品"),
        "finance_agent": ("财务", "报表", "预算"),
    })
    hit = router.route(_request("广告花费上涨，ROAS下降"))
    assert hit[0] == "commerce_agent"


def test_domain_router_finance():
    router = DomainRouter(domain_map={
        "commerce_agent": ("运营", "商品"),
        "finance_agent": ("财务", "预算"),
        "sales_agent": ("销售", "客户"),
    })
    assert router.route(_request("帮我看下财务预算"))[0] == "finance_agent"


def test_enterprise_router_pipeline_prefers_rule():
    rule = RuleRouter(keyword_map={"commerce_agent": ("广告",)})
    def llm(message, available):
        return {"candidates": ["finance_agent"]}
    router = EnterpriseAgentRouter(rule_router=rule, llm_router=LLMRouter(llm=llm))
    result = router.route(_request("广告问题"))
    assert result.selected_agent == "commerce_agent"
    assert result.layer == "rule"


def test_enterprise_router_llm_fallback():
    rule = RuleRouter(keyword_map={})
    def llm(message, available):
        return {"candidates": ["finance_agent"]}
    router = EnterpriseAgentRouter(rule_router=rule, llm_router=LLMRouter(llm=llm))
    result = router.route(_request("这个数字对不上"))
    assert result.selected_agent == "finance_agent"
    assert result.layer == "llm"


def test_llm_router_rejects_out_of_set_and_forbidden():
    def llm(message, available):
        return {"candidates": ["hacker_agent"], "tool": "db.query"}
    router = LLMRouter(llm=llm)
    assert router.route(_request("随便")) is None
