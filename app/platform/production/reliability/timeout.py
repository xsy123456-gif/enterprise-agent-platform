"""Timeout management (Phase 15.2)."""

import threading
from dataclasses import dataclass

from app.platform.production.errors import ExecutionTimeoutError


@dataclass(frozen=True)
class ExecutionTimeoutPolicy:
    agent_timeout: float = 300.0
    skill_timeout: float = 60.0
    tool_timeout: float = 30.0

    def for_component(self, component):
        if component == "agent":
            return self.agent_timeout
        if component == "skill":
            return self.skill_timeout
        if component == "tool":
            return self.tool_timeout
        return self.agent_timeout


def run_with_timeout(fn, timeout_seconds):
    result = {}
    error = {}

    def target():
        try:
            result["value"] = fn()
        except Exception as exc:  # noqa: BLE001 - re-raised to caller
            error["value"] = exc

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        raise ExecutionTimeoutError(
            f"execution exceeded {timeout_seconds}s timeout"
        )
    if "value" in error:
        raise error["value"]
    return result.get("value")


__all__ = ["ExecutionTimeoutPolicy", "run_with_timeout"]
