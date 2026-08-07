class MemoryAccessDenied(PermissionError):
    pass


class MemoryGovernancePolicy:
    """Legacy policy adapter; explicit rules are required for authorization."""

    def __init__(self, read_rule=None, write_rule=None):
        self.read_rule = read_rule
        self.write_rule = write_rule

    def check_read(self, request):
        allowed = self.read_rule(request) if self.read_rule else False
        if not allowed:
            raise MemoryAccessDenied("Memory read denied by governance policy")

    def check_write(self, event, candidate):
        allowed = self.write_rule(event, candidate) if self.write_rule else False
        if not allowed:
            raise MemoryAccessDenied("Memory write denied by governance policy")

    def authorize_ingest(self, principal, scope, source):
        if not self.read_rule or not self.read_rule(scope):
            raise MemoryAccessDenied("Memory ingest denied by governance policy")

    def authorize_read(self, principal, scope, requested_types):
        if not self.read_rule or not self.read_rule(scope):
            raise MemoryAccessDenied("Memory read denied by governance policy")
        from app.memory.ports.authorization import MemoryReadGrant
        return MemoryReadGrant(frozenset(requested_types or ()))

    def authorize_write_candidate(self, principal, scope, candidate_type):
        if not self.write_rule or not self.write_rule(scope, candidate_type):
            raise MemoryAccessDenied("Memory write denied by governance policy")
