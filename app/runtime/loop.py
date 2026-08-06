import json

from app.events.models import Event
from app.runtime.action import AgentAction
from app.runtime.context_builder import AgentContextBuilder
from app.runtime.trace import RuntimeTrace
from app.runtime.tool_validation import ToolRequestValidator


class AgentLoopError(RuntimeError):
    pass


class LoopStatus:
    CREATED = "created"
    CONTEXT_BUILDING = "context_building"
    THINKING = "thinking"
    WAITING_TOOL = "waiting_tool"
    TOOL_RUNNING = "tool_running"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentExecutionLoop:
    def __init__(
        self,
        agent_record,
        tool_runner,
        agent_registry=None,
        context_builder=None,
        max_steps=10,
    ):
        self.agent_record = agent_record
        self.agent = agent_record.instance
        self.tool_runner = tool_runner
        self.max_steps = max_steps
        self.tool_validator = ToolRequestValidator(tool_runner, agent_registry)
        self.context_builder = context_builder or AgentContextBuilder()

    def run(self, state):
        definition = self.agent_record.definition or getattr(
            self.agent, "definition", None
        )
        state.agent_definition = definition
        state.available_tools = self._available_tool_definitions(definition)
        trace = RuntimeTrace(
            trace_id=state.trace_id,
            task_id=getattr(state, "task_id", None),
            step_id=getattr(state, "step_id", None),
            agent_id=self.agent_record.agent_id,
            capability=getattr(state, "capability", None),
        )
        state.runtime_trace = trace
        self._transition(state, trace, LoopStatus.CREATED, "loop_started")
        self._publish(state, "agent_step_started", {})
        self._transition(
            state, trace, LoopStatus.CONTEXT_BUILDING, "context_built"
        )

        for step in range(1, self.max_steps + 1):
            self._transition(state, trace, LoopStatus.THINKING, "llm_call")
            trace.record(step, "llm_call", "started")
            try:
                response = self._reason(state, definition)
                trace.record(step, "llm_call", "completed")
                action = (
                    response
                    if isinstance(response, AgentAction)
                    else self._parse_action(response)
                )
            except Exception as error:
                self._transition(
                    state, trace, LoopStatus.FAILED, "agent_failed", str(error)
                )
                self._publish(state, "agent_failed", {"error": str(error)})
                raise AgentLoopError(str(error)) from error

            if action.type == AgentAction.FINISH:
                state.add_message("assistant", action.output)
                self._transition(
                    state, trace, LoopStatus.COMPLETED, "step_completed"
                )
                self._publish(state, "agent_step_completed", {"output": action.output})
                self._publish(state, "response.completed", {
                    "agent_id": self.agent_record.agent_id,
                    "user_id": state.user_id,
                    "tenant_id": getattr(state, "tenant_id", "default"),
                    "department_id": getattr(state, "department_id", None),
                    "input": state.task,
                    "output": action.output,
                    "tool_results": list(state.tool_results),
                    "metadata": {"capability": getattr(state, "capability", None)},
                })
                return action.output

            self._transition(state, trace, LoopStatus.WAITING_TOOL, "tool_requested")
            try:
                self.tool_validator.validate(action, state)
            except Exception as error:
                self._transition(
                    state, trace, LoopStatus.FAILED, "agent_failed", str(error)
                )
                self._publish(state, "agent_failed", {"error": str(error)})
                raise AgentLoopError(str(error)) from error
            self._transition(state, trace, LoopStatus.TOOL_RUNNING, "tool_call")
            self._publish(state, "tool_called", {"tool": action.tool})
            trace.record(step, "tool_call", "started", {"tool": action.tool})
            try:
                result = self.tool_runner.run(action, state)
            except Exception as error:
                self._transition(
                    state, trace, LoopStatus.FAILED, "agent_failed", str(error)
                )
                self._publish(state, "agent_failed", {"error": str(error)})
                raise AgentLoopError(str(error)) from error
            trace.record(step, "tool_call", "completed", {"tool": action.tool})
            self._transition(state, trace, LoopStatus.OBSERVING, "observation")
            self._publish(state, "agent_observation", {"result": result})
            state.add_message("user", f"Tool observation: {result}")

        error = "Agent exceeded max steps"
        self._transition(state, trace, LoopStatus.FAILED, "agent_failed", error)
        self._publish(state, "agent_failed", {"error": error})
        return {"error": error}

    def _messages(self, state, definition):
        return self.context_builder.build_messages(state, definition)

    def _reason(self, state, definition):
        if hasattr(self.agent, "reason"):
            return self.agent.reason(self._messages(state, definition))
        # Compatibility for pre-v0.4.3 custom Agents; new Agents should only
        # provide a definition and an LLM, leaving execution to this Loop.
        if hasattr(self.agent, "think"):
            return self.agent.think(state)
        raise AgentLoopError("Agent does not provide an LLM reasoning interface")

    def _available_tool_definitions(self, definition):
        definitions = []
        for name in getattr(definition, "allowed_tools", []):
            tool = self.tool_runner.registry.get(name)
            if tool is not None:
                definitions.append({
                    "name": name,
                    "description": getattr(tool, "description", ""),
                    "input_schema": getattr(tool, "input_schema", {}),
                })
        return definitions

    @staticmethod
    def _parse_action(response):
        if isinstance(response, str):
            text = response.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1]).strip()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = AgentExecutionLoop._extract_embedded_action(text)
                if data is None:
                    if text:
                        return AgentAction.finish_action(response)
                    raise ValueError("Agent response must not be empty")
        else:
            data = response
        if not isinstance(data, dict):
            raise ValueError("Agent response must be a JSON object")
        if data.get("type") == "tool" or data.get("action") == "tool_call":
            tool = data.get("tool")
            tool_input = data.get("input", data.get("arguments"))
            return AgentAction.tool_action(tool, tool_input)
        if data.get("type") == "finish" or data.get("action") == "finish":
            return AgentAction.finish_action(data.get("output"))
        raise ValueError("Invalid Agent action")

    @staticmethod
    def _extract_embedded_action(text):
        decoder = json.JSONDecoder()
        for position, character in enumerate(text):
            if character != "{":
                continue
            try:
                data, _ = decoder.raw_decode(text[position:])
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and (
                data.get("action") in {"tool_call", "finish"}
                or data.get("type") in {"tool", "finish"}
            ):
                return data
        return None

    @staticmethod
    def _transition(state, trace, status, action, detail=None):
        state.loop_status = status
        trace.record(getattr(state, "step_id", None), action, status, detail)

    def _publish(self, state, event_type, payload):
        event_bus = getattr(self.tool_runner, "event_bus", None)
        if event_bus is None:
            return
        event_bus.publish(
            Event(
                event_type,
                {
                    "trace_id": state.trace_id,
                    "task_id": getattr(state, "task_id", None),
                    "step_id": getattr(state, "step_id", None),
                    "agent": state.agent_name,
                    **payload,
                },
            )
        )
