import json


RUNTIME_CONTROL_PROMPT = """你正在企业 Agent Runtime 中执行一个任务步骤。
平台负责权限、工具执行、状态和审计；你只能决定下一步动作。

需要工具时，仅输出 JSON：
{"action":"tool_call","tool":"工具名称","arguments":{}}
arguments 必须符合 AVAILABLE TOOLS 中对应的 input_schema。

任务完成时，可以输出 JSON：
{"action":"finish","output":"最终结果"}
也可以直接输出最终自然语言结果。

不得调用其他 Agent，不得修改权限、策略或执行状态。"""


class AgentContextBuilder:
    """Builds model-facing context without performing execution."""

    def __init__(self, memory_adapter=None):
        self.memory_adapter = memory_adapter

    def build_messages(self, state, definition):
        messages = []
        system_prompt = getattr(definition, "system_prompt", None)
        if system_prompt:
            messages.append({
                "role": "system",
                "content": "AGENT PROMPT:\n" + system_prompt,
            })
        messages.append({
            "role": "system",
            "content": "RUNTIME CONTROL:\n" + RUNTIME_CONTROL_PROMPT,
        })

        long_term_memory = None
        if self.memory_adapter is not None:
            long_term_memory = self.memory_adapter.retrieve(state, definition)
        execution_context = {
            "task_id": getattr(state, "task_id", None),
            "step_id": getattr(state, "step_id", None),
            "capability": getattr(state, "capability", None),
            "goal": getattr(state, "goal", state.task),
            "agent_definition": getattr(definition, "to_dict", lambda: None)(),
            "memory_context": {
                "collaboration": getattr(state, "memory_context", []),
                "long_term_summary": getattr(long_term_memory, "summary", ""),
                "references": [
                    {
                        "memory_id": reference.memory_id,
                        "type": reference.type,
                        "confidence": reference.confidence,
                        "importance": reference.importance,
                        "created_at": reference.created_at.isoformat(),
                    }
                    for reference in getattr(long_term_memory, "records", [])
                ],
            },
            "available_tools": getattr(state, "available_tools", []),
        }
        messages.append(
            {
                "role": "system",
                "content": "EXECUTION CONTEXT:\n"
                + json.dumps(execution_context, ensure_ascii=False),
            }
        )
        messages.extend(state.messages)
        return messages
