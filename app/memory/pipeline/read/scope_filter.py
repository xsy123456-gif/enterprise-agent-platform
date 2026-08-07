from dataclasses import replace


class MemoryScopeFilter:
    def __init__(self, authorization_provider):
        self.authorization_provider = authorization_provider

    def authorize(self, request):
        grant = self.authorization_provider.authorize_read(
            request.principal, request.scope, request.types
        )
        return replace(request, types=list(grant.effective_types(request.types)))
