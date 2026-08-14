"""Agent admission — authorize before the Runtime/Worker starts."""

from app.integrations.security.models.trusted_principal import TrustedPrincipal
from app.permission.models.decision import Decision, PermissionDecision
from app.permission.models.environment import PermissionEnvironment
from app.permission.models.request import PermissionRequest
from app.permission.models.resource import PermissionResource


class AgentAdmissionController:
    def __init__(self, subject_resolver, permission_service):
        self.subject_resolver = subject_resolver
        self.permission_service = permission_service

    def admit(
        self,
        principal: TrustedPrincipal,
        agent_id: str,
        version: str | None,
        tenant_id: str,
        attributes: dict | None = None,
    ) -> PermissionDecision:
        subject = self.subject_resolver.resolve(principal)
        resource = PermissionResource(
            resource_type="agent",
            resource_id=agent_id,
            tenant_id=tenant_id,
            attributes=dict(attributes or {}) | {"version": version} if version else dict(attributes or {}),
        )
        request = PermissionRequest(
            request_id=f"admit:{agent_id}",
            subject=subject,
            resource=resource,
            action="invoke",
            environment=PermissionEnvironment(),
        )
        return self.permission_service.evaluate(request)

    def allowed(self, principal, agent_id, version, tenant_id, **kwargs) -> bool:
        decision = self.admit(principal, agent_id, version, tenant_id, **kwargs)
        return decision.decision is Decision.ALLOW
