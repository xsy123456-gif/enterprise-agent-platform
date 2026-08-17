"""Layer 2 Entity Router (Phase 12.3).

Recognizes subject identifiers (Store / Listing / SKU / Campaign) mentioned in
the message and attaches the resolved ``SubjectRef`` to the routing result so
the selected Skill can run against the right subject.  It never selects a skill
and never interprets cause.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class EntityMatch:
    token: str
    subject: object
    tenant_id: str = ""


class EntityRouter:

    def __init__(self, known_subjects=None, subject_tenants=None,
                 default_tenant=""):
        self.known_subjects = dict(known_subjects or {})
        self.subject_tenants = dict(subject_tenants or {})
        self.default_tenant = default_tenant

    def extract(self, message):
        found = []
        for token, subject in self.known_subjects.items():
            if token in (message or ""):
                found.append(EntityMatch(
                    token=token, subject=subject,
                    tenant_id=self.subject_tenants.get(token, self.default_tenant),
                ))
        return found


__all__ = ["EntityRouter", "EntityMatch"]
