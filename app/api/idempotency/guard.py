"""Idempotency guard (Phase 18.12.5).

Applies the Idempotency-Key header contract to command endpoints: same key +
same payload -> replay prior result; same key + different payload -> 409
IDEMPOTENCY_CONFLICT.  HTTP idempotency prevents duplicate command submission;
it is distinct from (and coexists with) Business Action idempotency.
"""

from dataclasses import dataclass

from app.api.errors import ApiError, ApiErrorCode
from app.api.idempotency.models import (
    IdempotencyRecord,
    is_valid_idempotency_key,
    request_fingerprint,
)


@dataclass
class IdempotencyToken:
    scope: tuple
    key: str
    fingerprint: str
    prior_result: str | None


class IdempotencyGuard:

    def __init__(self, store):
        self.store = store

    def resolve(self, request, ctx, operation, resource_id, payload):
        key = request.headers.get("Idempotency-Key")
        if not key:
            return None
        if not is_valid_idempotency_key(key):
            raise ApiError(ApiErrorCode.INVALID_REQUEST,
                           "Invalid Idempotency-Key.", http_status=400)
        scope = (ctx.trusted_context.tenant_id,
                 ctx.authenticated_principal.principal_id, operation)
        fingerprint = request_fingerprint(operation, resource_id, payload)
        existing = self.store.get(scope, key)
        if existing is not None:
            if existing.fingerprint != fingerprint:
                raise ApiError(
                    ApiErrorCode.IDEMPOTENCY_CONFLICT,
                    "Idempotency key was reused with a different request.",
                    http_status=409,
                )
            return IdempotencyToken(scope, key, fingerprint,
                                    existing.result_reference)
        return IdempotencyToken(scope, key, fingerprint, None)

    def record(self, token, result_reference):
        self.store.put(token.scope, token.key,
                       IdempotencyRecord(token.key, token.fingerprint,
                                         result_reference))


__all__ = ["IdempotencyGuard", "IdempotencyToken"]
