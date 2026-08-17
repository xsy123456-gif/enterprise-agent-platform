"""Response builder (Phase 12.7).

Converts a ``DiagnosticResult`` into employee language (``AgentResponse``).

The LLM may only polish / summarize / explain the *message text*.  The structured
``diagnostic_result``, its ``evidence`` / ``causes`` / ``priority`` are taken
verbatim from the DiagnosticResult — the LLM can never re-judge the cause.
"""

import uuid

from app.commerce.agents.domain import (
    RESPONSE_DIAGNOSTIC,
    AgentResponse,
)


class ResponseBuilder:

    def __init__(self, llm=None):
        self.llm = llm

    def build(self, diagnostic_result, request=None, memory_snippets=None):
        base = self._base_message(diagnostic_result)
        message = self._polish(base, diagnostic_result)
        return AgentResponse(
            response_id=uuid.uuid4().hex,
            session_id=getattr(request, "session_id", ""),
            response_type=RESPONSE_DIAGNOSTIC,
            message=message,
            diagnostic_result=diagnostic_result,
            evidence=tuple(getattr(diagnostic_result, "evidence", ()) or ()),
        )

    def _polish(self, base, diagnostic_result):
        if self.llm is None:
            return base
        try:
            polished = self.llm(base, diagnostic_result)
            if isinstance(polished, str) and polished.strip():
                return polished
        except Exception:  # noqa: BLE001 - polish failure falls back to base
            pass
        return base

    @staticmethod
    def _base_message(diagnostic_result):
        subject = diagnostic_result.subject
        subject_text = f"{subject.type}:{subject.id}"
        signals = "、".join(s.signal_code for s in diagnostic_result.signals) or "无"
        causes = "、".join(c.cause_code for c in diagnostic_result.causes) or "无"
        priority = getattr(diagnostic_result.priority, "level", "P3")
        return (
            f"针对 {subject_text} 的诊断（{diagnostic_result.status}）："
            f"检测到信号 {signals}；可能原因 {causes}；优先级 {priority}。"
        )


__all__ = ["ResponseBuilder"]
