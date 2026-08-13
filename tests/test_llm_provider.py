"""LLM provider decoupling tests: injectable planner + swappable providers."""

import unittest

from app.llm import BaseLLM, create_llm, registry
from app.capabilities.catalog import CapabilityCatalog
from app.capabilities.models import CapabilityDefinition
from app.capabilities.repository import InMemoryCapabilityRepository
from app.orchestration.llm_planner import LLMPlanner, LLMPlannerError
from app.orchestration.planner import BasicPlanner
from app.orchestration.task import Task
from app.orchestration.validator import PlanValidator


class MockLLM(BaseLLM):
    """A deterministic LLM that returns a fixed valid plan."""

    provider = "mock"

    def __init__(self, response=None):
        self.response = response or (
            '{"goal":"Analyze", "steps":['
            '{"step_id":"1","capability":"customer_analysis",'
            '"dependencies":[]}]}'
        )
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        return self.response


def _catalog():
    catalog = CapabilityCatalog(InMemoryCapabilityRepository())
    catalog.register(
        CapabilityDefinition(
            capability_id="customer_analysis",
            name="Customer analysis",
            description="Analyze customers",
        )
    )
    return catalog


class LLMPlannerInjectionTest(unittest.TestCase):
    def test_planner_generates_plan_with_mock_llm(self):
        llm = MockLLM()
        plan = LLMPlanner(
            llm=llm,
            catalog=_catalog(),
            validator=PlanValidator(_catalog()),
        ).plan(Task(user_query="Analyze customer"))
        self.assertEqual("customer_analysis", plan.steps[0].capability)
        self.assertEqual(1, llm.calls)

    def test_planner_requires_llm(self):
        with self.assertRaises(LLMPlannerError):
            LLMPlanner(llm=None, catalog=_catalog())

    def test_planner_falls_back_when_mock_llm_fails(self):
        class BrokenMockLLM(MockLLM):
            def chat(self, messages, **kwargs):
                raise ConnectionError("offline")

        planner = LLMPlanner(
            llm=BrokenMockLLM(),
            catalog=_catalog(),
            validator=PlanValidator(_catalog()),
            fallback=BasicPlanner(),
        )
        plan = planner.plan(Task(user_query="anything"))
        self.assertEqual("customer_analysis", plan.steps[0].capability)


class LLMProviderRegistryTest(unittest.TestCase):
    def test_default_provider_is_deepseek(self):
        llm = create_llm()
        self.assertIsInstance(llm, BaseLLM)
        self.assertEqual("deepseek", llm.provider)

    def test_registry_lists_deepseek(self):
        self.assertIn("deepseek", registry.names())

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValueError):
            create_llm(provider="nonexistent")

    def test_provider_can_be_swapped_via_registry(self):
        registry.register("mock", MockLLM)
        try:
            llm = create_llm(provider="mock")
            self.assertIsInstance(llm, MockLLM)
            self.assertEqual("mock", llm.provider)
        finally:
            # do not leak the mock provider into other tests
            registry._providers.pop("mock", None)


if __name__ == "__main__":
    unittest.main()
