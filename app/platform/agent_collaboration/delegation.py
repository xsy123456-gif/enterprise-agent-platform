"""Delegation runtime (Phase 14.3).

Agent A calls Agent B only through ``DelegationExecutor`` (never by importing
Agent B).  The executor performs the collaboration-governance check and then
invokes the Runtime Plane via an injected ``agent_runner`` callable.
"""

from app.platform.agent_collaboration.domain import (
    DELEGATION_FAILED,
    DELEGATION_SUCCEEDED,
    AgentDelegationRequest,
    AgentDelegationResult,
)


class DelegationExecutor:

    def __init__(self, agent_runner, access_control=None):
        self.agent_runner = agent_runner
        self.access_control = access_control

    def execute(self, request: AgentDelegationRequest) -> AgentDelegationResult:
        if self.access_control is not None:
            self.access_control.authorize(request.from_agent_id,
                                          request.to_agent_id)
        try:
            outcome = self.agent_runner(
                request.to_agent_id, request.goal, request.input_context_ref
            )
        except Exception as error:  # noqa: BLE001 - surfaced as typed result
            return AgentDelegationResult(
                delegation_id=request.delegation_id,
                agent_id=request.to_agent_id,
                status=DELEGATION_FAILED,
                summary=str(error),
            )
        outcome = outcome or {}
        return AgentDelegationResult(
            delegation_id=request.delegation_id,
            agent_id=request.to_agent_id,
            status=DELEGATION_SUCCEEDED,
            result_reference=outcome.get("result_reference", ""),
            summary=outcome.get("summary", ""),
        )


__all__ = ["DelegationExecutor"]
