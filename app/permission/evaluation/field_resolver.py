"""Safe field resolver.

Only ``subject.*`` / ``resource.*`` / ``environment.*`` / ``action`` may be
read.  No arbitrary getattr traversal.  A ``MISSING`` sentinel distinguishes a
fact that does not exist from a fact whose value is ``None``.
"""

from app.permission.errors import PermissionEvaluationError

MISSING = object()

_SUBJECT_FIELDS = {
    "subject_id", "tenant_id", "roles", "department_id", "position_id",
    "professional_level", "security_clearance", "scopes",
}
_RESOURCE_FIELDS = {"resource_type", "resource_id", "tenant_id"}


def resolve_field(request, field: str):
    parts = field.split(".")
    if not parts:
        raise PermissionEvaluationError("empty field")
    root = parts[0]
    if root == "action":
        return request.action
    if root == "subject":
        return _resolve_subject(request.subject, parts[1:])
    if root == "resource":
        return _resolve_resource(request.resource, parts[1:])
    if root == "environment":
        return _resolve_environment(request.environment, parts[1:])
    raise PermissionEvaluationError(f"unknown field root: {root}")


def _resolve_subject(subject, parts):
    if not parts:
        return subject
    key = parts[0]
    if key == "attributes":
        return _resolve_attributes(subject.attributes, parts[1:])
    if key in _SUBJECT_FIELDS:
        return getattr(subject, key)
    raise PermissionEvaluationError(f"unknown subject field: {key}")


def _resolve_resource(resource, parts):
    if not parts:
        return resource
    key = parts[0]
    if key == "attributes":
        return _resolve_attributes(resource.attributes, parts[1:])
    if key in _RESOURCE_FIELDS:
        return getattr(resource, key)
    raise PermissionEvaluationError(f"unknown resource field: {key}")


def _resolve_environment(environment, parts):
    if not parts:
        return environment
    key = parts[0]
    if key == "attributes":
        return _resolve_attributes(environment.attributes, parts[1:])
    raise PermissionEvaluationError(f"unknown environment field: {key}")


def _resolve_attributes(attributes, parts):
    if not parts:
        return attributes
    key = parts[0]
    if key not in attributes:
        return MISSING
    return attributes[key]
