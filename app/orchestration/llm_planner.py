import json

from app.llm.factory import create_llm
from app.orchestration.planner import Planner


PLANNER_SYSTEM_PROMPT = """
你是企业 Agent 平台的任务规划器。

将用户任务拆解为可执行的业务能力步骤，只能输出 JSON：
{
  "goal": "任务目标",
  "steps": [
    {
      "step_id": "1",
      "capability": "能力标识",
      "dependencies": []
    }
  ]
}

规则：
- 只描述业务 Capability，不选择 Agent。
- 不得输出 agent、agent_id、tool、tool_name、permission 或 runtime。
- dependencies 必须引用其他 step_id。
- 不要输出 Markdown、解释或额外字段。
"""


class LLMPlannerError(RuntimeError):
    pass


class LLMPlannerUnavailable(LLMPlannerError):
    pass


class LLMPlanner(Planner):
    def __init__(self, llm=None, catalog=None, validator=None, fallback=None):
        self.llm = llm or create_llm()
        self.catalog = catalog
        self.validator = validator
        self.fallback = fallback

    def plan(self, task):
        if self.catalog is None:
            raise LLMPlannerError("LLMPlanner requires a CapabilityCatalog")

        catalog_context = self.catalog.format_catalog_context()
        system_prompt = (
            PLANNER_SYSTEM_PROMPT
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
