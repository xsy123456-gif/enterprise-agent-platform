"""Agent publishing (Phase 15.6).

Developer -> Submit -> Review -> Approve -> Publish (into the catalog).  A
state machine: publishing never skips review, and only APPROVED agents publish.
"""

from dataclasses import dataclass

from app.platform.production.errors import ProductionError
from app.platform.production.marketplace.catalog import AgentCatalog

PUBLISH_SUBMITTED = "SUBMITTED"
PUBLISH_REVIEW = "REVIEW"
PUBLISH_APPROVED = "APPROVED"
PUBLISH_PUBLISHED = "PUBLISHED"
PUBLISH_REJECTED = "REJECTED"
PUBLISH_STATUSES = frozenset({
    PUBLISH_SUBMITTED, PUBLISH_REVIEW, PUBLISH_APPROVED, PUBLISH_PUBLISHED,
    PUBLISH_REJECTED,
})

_TRANSITIONS = {
    PUBLISH_SUBMITTED: {PUBLISH_REVIEW},
    PUBLISH_REVIEW: {PUBLISH_APPROVED, PUBLISH_REJECTED},
    PUBLISH_APPROVED: {PUBLISH_PUBLISHED},
    PUBLISH_REJECTED: set(),
    PUBLISH_PUBLISHED: set(),
}


class AgentPublisher:

    def __init__(self, catalog=None):
        self.catalog = catalog or AgentCatalog()
        self._status = {}

    def submit(self, entry):
        self._status[entry.agent_id] = PUBLISH_SUBMITTED
        return PUBLISH_SUBMITTED

    def review(self, agent_id):
        return self._transition(agent_id, PUBLISH_REVIEW)

    def approve(self, agent_id):
        return self._transition(agent_id, PUBLISH_APPROVED)

    def reject(self, agent_id):
        return self._transition(agent_id, PUBLISH_REJECTED)

    def publish(self, agent_id):
        self._transition(agent_id, PUBLISH_PUBLISHED)
        self.catalog.add(self._entry(agent_id))
        return PUBLISH_PUBLISHED

    def status(self, agent_id):
        return self._status.get(agent_id)

    def _transition(self, agent_id, target):
        current = self._status.get(agent_id)
        if current is None:
            raise ProductionError(f"agent {agent_id!r} was not submitted")
        if target not in _TRANSITIONS[current]:
            raise ProductionError(
                f"cannot move agent {agent_id!r} from {current!r} to {target!r}"
            )
        self._status[agent_id] = target
        return target

    def _entry(self, agent_id):
        from app.platform.production.marketplace.catalog import AgentCatalogEntry
        return AgentCatalogEntry(agent_id=agent_id)


__all__ = [
    "AgentPublisher",
    "PUBLISH_SUBMITTED",
    "PUBLISH_REVIEW",
    "PUBLISH_APPROVED",
    "PUBLISH_PUBLISHED",
    "PUBLISH_REJECTED",
    "PUBLISH_STATUSES",
]
