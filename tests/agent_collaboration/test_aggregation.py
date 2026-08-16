"""Phase 14.5 Aggregation tests."""

from app.platform.agent_collaboration.aggregator import (
    AgentResultAggregator,
    AgentResultItem,
    ConflictResolver,
    EVIDENCE_AGENT_OPINION,
    EVIDENCE_DIAGNOSTIC,
    EVIDENCE_LLM_SUMMARY,
)


def test_aggregate_multiple_results():
    aggregator = AgentResultAggregator()
    result = aggregator.aggregate("t1", [
        AgentResultItem(agent_id="sales_agent", summary="整体下滑",
                        confidence=0.9, topic="sales"),
        AgentResultItem(agent_id="commerce_agent", summary="库存不足",
                        confidence=0.8, topic="commerce"),
        AgentResultItem(agent_id="marketing_agent", summary="流量下降",
                        confidence=0.7, topic="marketing"),
    ])
    assert result.agent_results and len(result.agent_results) == 3
    assert "库存不足" in result.summary
    assert result.confidence == 0.7  # min (conservative)


def test_conflict_resolver_prioritizes_diagnostic_evidence():
    resolver = ConflictResolver()
    items = [
        AgentResultItem(agent_id="commerce_agent", summary="库存不足",
                        evidence_type=EVIDENCE_DIAGNOSTIC),
        AgentResultItem(agent_id="marketing_agent", summary="广告流量下降",
                        evidence_type=EVIDENCE_AGENT_OPINION),
        AgentResultItem(agent_id="sales_agent", summary="可能是天气原因",
                        evidence_type=EVIDENCE_LLM_SUMMARY),
    ]
    winner = resolver.resolve(items)
    assert winner.summary == "库存不足"


def test_aggregate_detects_and_resolves_conflict():
    aggregator = AgentResultAggregator()
    result = aggregator.aggregate("t1", [
        AgentResultItem(agent_id="commerce_agent", summary="库存不足",
                        evidence_type=EVIDENCE_DIAGNOSTIC, topic="root_cause",
                        confidence=0.9),
        AgentResultItem(agent_id="marketing_agent", summary="广告流量下降",
                        evidence_type=EVIDENCE_AGENT_OPINION, topic="root_cause",
                        confidence=0.8),
    ])
    assert len(result.conflicts) == 1
    assert result.conflicts[0].resolved == "库存不足"
    assert result.conflicts[0].alternatives == ("广告流量下降",)
