"""Knowledge projection service (Phase 18.11).

Bridges the Management Plane -> Serving Plane: on document activation, the
projection pushes the ACTIVE (document, content) into the ``KnowledgeServingPort``.
"""


class KnowledgeProjectionService:

    def __init__(self, serving_port):
        self.serving_port = serving_port

    def project(self, document, content):
        return self.serving_port.project(document, content)


__all__ = ["KnowledgeProjectionService"]
