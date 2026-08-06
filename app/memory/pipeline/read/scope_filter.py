class MemoryScopeFilter:
    def __init__(self, governance):
        self.governance = governance

    def authorize(self, request):
        self.governance.check_read(request)
        return request
