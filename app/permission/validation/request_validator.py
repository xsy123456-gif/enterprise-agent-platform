"""Request validation — fail-closed."""

import re

from app.permission.errors import PermissionValidationError
from app.permission.models.request import PermissionRequest

_ACTION_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_JSON_SCALARS = (str, int, float, bool, type(None))


def _is_json_safe(value):
    if isinstance(value, _JSON_SCALARS):
        if isinstance(value, float):
            import math

            return math.isfinite(value)
        return True
    if isinstance(value, (list, tuple)):
        return all(_is_json_safe(item) for item in value)
    if isinstance(value, dict):
        return all(
            isinstance(key, str) and _is_json_safe(item)
            for key, item in value.items()
        )
    return False


def validate_request(request: PermissionRequest) -> None:
    errors = []
    if not isinstance(request, PermissionRequest):
        raise PermissionValidationError("request must be a PermissionRequest")
    if not request.request_id:
        errors.append("request_id required")
    if not request.subject.subject_id:
        errors.append("subject.subject_id required")
    if not request.subject.tenant_id:
        errors.append("subject.tenant_id required")
    if not request.resource.resource_type:
        errors.append("resource.resource_type required")
    if not request.resource.resource_id:
        errors.append("resource.resource_id required")
    if not request.resource.tenant_id:
        errors.append("resource.tenant_id required")
    if not request.action or not _ACTION_RE.match(request.action):
        errors.append(f"invalid action: {request.action!r}")
    if not _is_json_safe(request.subject.attributes):
        errors.append("subject.attributes not JSON-safe")
    if not _is_json_safe(request.resource.attributes):
        errors.append("resource.attributes not JSON-safe")
    if not _is_json_safe(request.environment.attributes):
        errors.append("environment.attributes not JSON-safe")
    if errors:
        raise PermissionValidationError("; ".join(errors))
