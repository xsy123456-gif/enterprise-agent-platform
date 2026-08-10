import unittest
from unittest.mock import patch

from app.runtime.backends.langgraph import (
    GraphState,
    LangGraphRuntimeAdapter,
    LangGraphStateMapper,
    build_graph,
)
from app.runtime.selector import RuntimeSelector


class LangGraphRuntimeSkeletonTest(unittest.TestCase):
    def test_runtime_can_be_created_without_business_dependencies(self):
        self.assertIsInstance(LangGraphRuntimeAdapter(), LangGraphRuntimeAdapter)

    def test_graph_initializes(self):
        self.assertIsNotNone(build_graph())

    def test_selector_supports_named_langgraph_backend(self):
        current = LangGraphRuntimeAdapter()
        langgraph = LangGraphRuntimeAdapter()
        selector = RuntimeSelector({"current": current, "langgraph": langgraph})

        self.assertIs(langgraph, selector.select("langgraph"))
        self.assertIs(langgraph, selector.select())

        with patch.dict("os.environ", {"RUNTIME_BACKEND": "langgraph"}):
            self.assertIs(langgraph, selector.select())

    def test_skeleton_graph_executes_without_business_nodes(self):
        state: GraphState = {"trace_id": "test", "metadata": {}}

        result = build_graph().invoke(state)

        self.assertEqual("test", result["trace_id"])

    def test_state_mapper_preserves_runtime_contract(self):
        from app.runtime.contracts import AgentRuntimeState
        runtime_state = AgentRuntimeState(
            "task", "trace", "tenant", "agent", "1",
            metadata={"execution_id": "execution", "task": "input"},
        )
        mapper = LangGraphStateMapper()

        graph_state = mapper.to_graph_state(runtime_state)
        result = mapper.from_graph_state(graph_state)
        restored = mapper.apply_result(runtime_state, result)

        self.assertEqual("execution", graph_state["execution_id"])
        self.assertEqual("input", graph_state["input"])
        self.assertEqual(runtime_state, restored)
