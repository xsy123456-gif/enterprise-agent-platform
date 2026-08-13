"""Knowledge document lifecycle states.

Normal retrieval only surfaces ``active`` documents.  Deletion is a tombstone
(``inactive``) first, with physical removal done asynchronously.
"""

from enum import Enum


class KnowledgeDocumentStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


RETRIEVABLE = {KnowledgeDocumentStatus.ACTIVE}
