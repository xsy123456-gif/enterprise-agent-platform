"""Knowledge composition wiring (Phase 18.11).

Assembles the Knowledge Management Plane -> Projection -> Serving Plane, and a
thin ``ServingKnowledgeAgentAdapter`` that implements the Employee Agent's
``AgentKnowledgePort`` over the serving port (never over management objects).
"""

from types import SimpleNamespace

from app.commerce.agents.context import AgentKnowledgePort


class ServingKnowledgeAgentAdapter(AgentKnowledgePort):
    """Employee Agent knowledge boundary -> Knowledge Serving Plane."""

    def __init__(self, serving_port, tenant_id="", agent_id=""):
        self.serving_port = serving_port
        self.tenant_id = tenant_id
        self.agent_id = agent_id

    def retrieve(self, query):
        return self.serving_port.retrieve(query, self.tenant_id, self.agent_id)


def build_knowledge_wiring(access_control=None):
    from app.platform.production.knowledge import (
        InMemoryKnowledgeManagementRepository,
        InMemoryKnowledgeServing,
        KnowledgeIngestionService,
        KnowledgeProjectionService,
    )
    serving = InMemoryKnowledgeServing(access_control=access_control)
    projection = KnowledgeProjectionService(serving)
    management = KnowledgeIngestionService(
        repository=InMemoryKnowledgeManagementRepository(),
        projection=projection,
        access_control=access_control,
    )
    return SimpleNamespace(
        management=management,
        serving=serving,
        projection=projection,
    )


__all__ = ["ServingKnowledgeAgentAdapter", "build_knowledge_wiring"]
