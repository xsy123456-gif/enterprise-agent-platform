from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from app.main import build_orchestration
from tests.memory.repository import TestEmbeddingService, TestMemoryRepository
from app.orchestration.task import Task
from tests.test_orchestration import PlannerAndAgentStubLLM


def test_production_langgraph_builds_queryable_node_and_tool_timeline():
    llm = PlannerAndAgentStubLLM()
    with patch("app.main.create_llm", return_value=llm):
        planner, supervisor, _, _ = build_orchestration(
            activate_builtin=True,
            memory_repository=TestMemoryRepository(),
            memory_embedding_service=TestEmbeddingService(),
        )
    plan = planner.plan(Task(user_query="准备客户A拜访资料"))
    with redirect_stdout(StringIO()):
        result = supervisor.execute(plan, "sales_001", "sales")
    dispatcher = supervisor.runtime
    dispatcher.trace_consumer.drain(2)
    traces = dispatcher.trace_query.get_by_execution(plan.task_id)
    assert result.output == "visit prepared"
    assert traces
    assert all(trace.artifact_hash != "unknown" for trace in traces)
    spans = [
        span for trace in traces
        for span in dispatcher.trace_query.span_tree(trace.trace_id)
    ]
    assert any(getattr(span, "span_type", None) == "NODE" for span in spans)
    tool_spans = [span for span in spans if getattr(span, "span_type", None) == "TOOL"]
    assert tool_spans and tool_spans[0].status == "OK"
    assert tool_spans[0].parent_span_id is not None
    dispatcher.trace_consumer.close()
