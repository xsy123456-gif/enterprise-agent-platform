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


class EntityRouter:

    def __init__(self, known_subjects=None):
        self.known_subjects = dict(known_subjects or {})

    def extract(self, message):
        found = []
        for token, subject in self.known_subjects.items():
            if token in (message or ""):
                found.append(EntityMatch(token=token, subject=subject))
        return found


__all__ = ["EntityRouter", "EntityMatch"]
