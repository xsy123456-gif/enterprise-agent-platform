class MemoryAccessDenied(PermissionError):
    pass


class MemoryGovernancePolicy:
    """Default tenant/user/Agent isolation policy; deployments may inject stricter rules."""

    def __init__(self, read_rule=None, write_rule=None):
        self.read_rule = read_rule
        self.write_rule = write_rule

    def check_read(self, request):
        allowed = self.read_rule(request) if self.read_rule else bool(
            request.tenant_id and request.user_id and request.agent_id
        )
        if not allowed:
            raise MemoryAccessDenied("Memory read denied by governance policy")

    def check_write(self, event, candidate):
        allowed = self.write_rule(event, candidate) if self.write_rule else bool(
            event.tenant_id and event.user_id and event.agent_id
        )
        if not allowed:
            raise MemoryAccessDenied("Memory write denied by governance policy")
