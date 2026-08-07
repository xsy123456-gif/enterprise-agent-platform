class MemoryScopeFilter:
    def __init__(self, authorization_provider):
        self.authorization_provider = authorization_provider

    def authorize(self, request):
        grant = self.authorization_provider.authorize_read(
            request.principal, request.scope, request.types
        )
        if not grant.permits(request.types):
            raise PermissionError("Memory read denied for requested types")
        return request
