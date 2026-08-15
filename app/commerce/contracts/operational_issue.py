"""OperationalIssue contract surface.

``OperationalIssue`` is defined once in the operations domain (the persisted,
tenant-scoped canonical entity) and re-exported here as the diagnostic-output
contract, so it appears both in the entity graph and the contract layer without
duplication.
"""

from app.commerce.domain.operations import OperationalIssue

__all__ = ["OperationalIssue"]
