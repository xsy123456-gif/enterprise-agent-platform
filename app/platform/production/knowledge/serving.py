"""Knowledge serving plane (Phase 18.11).

The SINGLE serving truth for agent-facing knowledge retrieval.  The Management
Plane projects ACTIVE documents here; the Serving Plane enforces ACL and returns
snippets/citations.  No independent retrieval/vector pipeline exists elsewhere.
"""

from abc import ABC, abstractmethod


class KnowledgeServingPort(ABC):
    @abstractmethod
    def project(self, document, content):
        pass

    @abstractmethod
    def retrieve(self, query, tenant_id, agent_id):
        pass


class InMemoryKnowledgeServing(KnowledgeServingPort):

    def __init__(self, access_control=None):
        self._active = {}  # document_id -> (document, content)
        self.access_control = access_control

    def project(self, document, content):
        self._active[document.document_id] = (document, content)

    def retrieve(self, query, tenant_id, agent_id):
        results = []
        for document_id, (document, content) in self._active.items():
            if document.tenant_id != tenant_id:
                continue
            if self.access_control is not None \
                    and not self.access_control.check(document_id, agent_id):
                continue
            if query.lower() in content.lower():
                results.append(content)
        return results


__all__ = ["KnowledgeServingPort", "InMemoryKnowledgeServing"]
