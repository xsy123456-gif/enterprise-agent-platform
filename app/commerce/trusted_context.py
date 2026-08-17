"""Trusted execution context projection for the Commerce tool surface.

``TrustedExecutionContext`` (Phase 5) is the immutable trusted projection of the
Platform AccessContext + Runtime metadata.  It is produced ONLY by the platform
(from a resolved ``PermissionSubject``), never by an Agent / Skill / Plan / LLM,
and carried to the read tools via a ``ContextVar`` so a request can never set
tenant / principal / scope / permission.
"""

from contextvars import ContextVar

from app.commerce.diagnostics.plans.ports import TrustedExecutionContext

_current: ContextVar = ContextVar("commerce_trusted_context", default=None)

SCOPE_DIMENSION_STORE = "business.store"


def set_trusted_context(context):
    return _current.set(context)


def reset_trusted_context(token):
    _current.reset(token)


def current_trusted_context():
    return _current.get()


def project_trusted_context(subject, metadata=None):
    """Project a resolved ``PermissionSubject`` + runtime metadata into a
    ``TrustedExecutionContext``.  Scopes are flattened to ``dimension:value``.

    ``permissions`` is left EMPTY: the Platform currently does not expose a
    static effective-permission grant list on the subject, so Commerce must NOT
    derive permissions from roles.  Actual authorization remains with the
    Platform PermissionSubject / ExecutionSecurityGate.
    """
    metadata = metadata or {}
    scopes = []
    for grant in getattr(subject.scopes, "grants", ()) or ():
        for value in sorted(grant.values):
            scopes.append(f"{grant.dimension}:{value}")
    return TrustedExecutionContext(
        tenant_id=subject.tenant_id,
        principal_id=subject.subject_id,
        organization_id=metadata.get("organization_id", ""),
        scopes=tuple(scopes),
        permissions=(),
        trace_id=metadata.get("trace_id", ""),
        execution_id=metadata.get("execution_id", ""),
        environment=metadata.get("environment", ""),
    )


def store_in_scope(store_id, trusted):
    """STRICT scope check: a store id is authorized only if it is in the
    trusted context's ``business.store`` scope."""
    if trusted is None:
        return False
    return f"{SCOPE_DIMENSION_STORE}:{store_id}" in (trusted.scopes or ())


__all__ = [
    "set_trusted_context",
    "reset_trusted_context",
    "current_trusted_context",
    "project_trusted_context",
    "store_in_scope",
    "SCOPE_DIMENSION_STORE",
]
