"""Agent public mapper (Phase 18.12)."""

from app.api.v1.schemas.agents import AgentSummary


def agent_summary_from(definition) -> AgentSummary:
    return AgentSummary(
        agent_id=definition.agent_id,
        name=getattr(definition, "name", "") or definition.agent_id,
        description=getattr(definition, "description", ""),
        version=getattr(definition, "version", ""),
        domain=getattr(definition, "domain", ""),
        status=getattr(definition, "status", "ACTIVE"),
    )


__all__ = ["agent_summary_from"]
