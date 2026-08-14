"""Permission request — immutable authorization fact snapshot."""

from dataclasses import dataclass

from app.permission.models.environment import PermissionEnvironment
from app.permission.models.resource import PermissionResource
from app.permission.models.subject import PermissionSubject


@dataclass(frozen=True)
class PermissionRequest:
    request_id: str
    subject: PermissionSubject
    resource: PermissionResource
    action: str
    environment: PermissionEnvironment = PermissionEnvironment()
