"""Commerce repository implementations.

The ``ports`` package holds the abstract repository boundary; ``postgres`` and
``inmemory`` provide the production and test/development implementations behind
the same interface, so the Query Service never depends on psycopg.
"""

from app.commerce.repositories.ports import CommerceRepository, ExternalIdentityMap

__all__ = ["CommerceRepository", "ExternalIdentityMap"]
