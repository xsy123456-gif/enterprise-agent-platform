from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class MemoryReadGrant:
    """The authorization result, not merely a boolean permission check.

    ``None`` means allow every type; an empty set means deny every type.
    """

    allowed_types: frozenset[str] | None = field(default_factory=frozenset)

    @classmethod
    def allow_all(cls):
        return cls(None)

    @classmethod
    def deny_all(cls):
        return cls(frozenset())

    def effective_types(self, requested_types):
        requested = frozenset(requested_types)
        if self.allowed_types is None:
            return requested
        if not self.allowed_types:
            raise PermissionError("Memory read denied for every type")
        if requested and not requested.issubset(self.allowed_types):
            raise PermissionError("Memory read denied for requested types")
        return requested or self.allowed_types


class MemoryAuthorizationProvider(Protocol):
    def authorize_ingest(self, principal, scope, source) -> None:
        ...

    def authorize_read(self, principal, scope, requested_types) -> MemoryReadGrant:
        ...

    def authorize_write_candidate(self, principal, scope, candidate_type) -> None:
        ...


class AllowAllMemoryAuthorizationProvider:
    """Explicit test/development policy; never used as a production default."""

    def authorize_ingest(self, principal, scope, source):
        return None

    def authorize_read(self, principal, scope, requested_types):
        return MemoryReadGrant.allow_all()

    def authorize_write_candidate(self, principal, scope, candidate_type):
        return None


class DenyByDefaultMemoryAuthorizationProvider:
    def authorize_ingest(self, principal, scope, source):
        raise PermissionError("Memory ingest authorization is required")

    def authorize_read(self, principal, scope, requested_types):
        raise PermissionError("Memory read authorization is required")

    def authorize_write_candidate(self, principal, scope, candidate_type):
        raise PermissionError("Memory write authorization is required")
