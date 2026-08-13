import json

from app.orchestration.planner import Planner
from app.prompts.planner import PLANNER_PROMPT


class LLMPlannerError(RuntimeError):
    pass


class LLMPlannerUnavailable(LLMPlannerError):
    pass


class LLMPlanner(Planner):
    """LLM-backed planner.

    The LLM is injected via ``BaseLLM``; the planner never creates or selects a
    provider.  Provider wiring belongs to the composition root (``main.py``).
    """

    def __init__(self, llm, catalog=None, validator=None, fallback=None):
        if llm is None:
            raise LLMPlannerError("LLMPlanner requires an injected LLM (BaseLLM)")
        self.llm = llm
        self.catalog = catalog
        self.validator = validator
        self.fallback = fallback

    def plan(self, task):
        if self.catalog is None:
            raise LLMPlannerError("LLMPlanner requires a CapabilityCatalog")

        catalog_context = self.catalog.format_catalog_context()
        system_prompt = (
            PLANNER_PROMPT
            + "\n你只能从以下 Capability Catalog 中选择 capability_id，禁止创造新能力：\n"
            + catalog_context
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "user_query": task.user_query,
                        "context": task.context,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        try:
            response = self.llm.chat(messages)
        except Exception as error:
            if self.fallback is not None:
                return self.fallback.plan(task)
            raise LLMPlannerUnavailable("LLM planner is unavailable") from error

        if self.validator is None:
            raise LLMPlannerError("LLMPlanner requires a PlanValidator")
        return self.validator.parse_and_validate(task, response)
