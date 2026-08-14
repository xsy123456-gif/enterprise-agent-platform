"""Permission-backed lifecycle authorization adapter."""

from app.permission.models.environment import PermissionEnvironment
from app.permission.models.request import PermissionRequest
from app.permission.models.resource import PermissionResource


class PermissionLifecycleAuthorizationAdapter:
    """Authorize agent-lifecycle actions via the Permission foundation.

    Implements the governance-side ``LifecycleAuthorizationPort`` contract.
    """

    def __init__(self, subject_resolver, permission_service):
        self.subject_resolver = subject_resolver
        self.permission_service = permission_service

    def authorize(self, principal, action, agent_id, version) -> bool:
        subject = self.subject_resolver.resolve(principal)
        resource = PermissionResource(
            resource_type="agent_definition",
            resource_id=agent_id,
            tenant_id=subject.tenant_id,
            attributes={"version": version} if version else {},
        )
        request = PermissionRequest(
            request_id=f"lifecycle:{action}:{agent_id}",
            subject=subject,
            resource=resource,
            action=action,
            environment=PermissionEnvironment(),
        )
        return self.permission_service.evaluate(request).allowed
