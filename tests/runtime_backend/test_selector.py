import unittest
from unittest.mock import patch

from app.agents.definition import AgentDefinition
from app.runtime.contracts import ExecutionResult
from app.runtime.ports import GraphRuntime
from app.runtime.selector import RuntimeSelector


class _Runtime(GraphRuntime):
    def execute(self, artifact, state) -> ExecutionResult:
        raise NotImplementedError


class RuntimeSelectorTest(unittest.TestCase):
    def setUp(self):
        self.current = _Runtime()
        self.langgraph = _Runtime()
        self.selector = RuntimeSelector({
            "current": self.current,
            "langgraph": self.langgraph,
        })

    def test_langgraph_is_default_and_current_is_explicit_legacy(self):
        self.assertIs(self.langgraph, self.selector.select("agent", "1.0"))
        self.assertIs(
            self.current,
            self.selector.select(
                "agent", "1.0", feature_flags={"runtime_backend": "current"}
            ),
        )
        with patch.dict("os.environ", {"RUNTIME_BACKEND": "current"}):
            self.assertIs(self.current, self.selector.select("agent", "1.0"))

    def test_select_langgraph_backend(self):
        definition = AgentDefinition(
            "agent", "1.0", "prompt", runtime={"backend": "langgraph"},
        )
        self.assertIs(
            self.langgraph,
            self.selector.select("agent", "1.0", agent_definition=definition),
        )
        self.assertIs(
            self.langgraph,
            self.selector.select(
                "agent", "1.0", feature_flags={"runtime_backend": "langgraph"},
            ),
        )
