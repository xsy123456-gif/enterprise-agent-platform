from datetime import datetime, timezone
import time


class RuntimeTrace:
    def __init__(
        self,
        trace_id=None,
        task_id=None,
        step_id=None,
        agent_id=None,
        capability=None,
    ):
        self.trace_id = trace_id
        self.task_id = task_id
        self.step_id = step_id
        self.agent_id = agent_id
        self.capability = capability
        self.steps = []
        self.llm_calls = 0
        self.tool_calls = 0
        self.started_at = self._now()
        self._started_monotonic = time.monotonic()

    def record(self, step, action, status, detail=None):
        self.steps.append(
            {
                "step": step,
                "action": action,
                "status": status,
                "detail": detail,
                "time": self._now(),
            }
        )
        if action == "llm_call":
            self.llm_calls += 1
        if action == "tool_call":
            self.tool_calls += 1

    def all(self):
        return self.steps

    def to_dict(self):
        return {
            "trace_id": self.trace_id,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "agent_id": self.agent_id,
            "capability": self.capability,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "duration": time.monotonic() - self._started_monotonic,
            "steps": list(self.steps),
        }

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()
