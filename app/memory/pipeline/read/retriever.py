class MemoryRetriever:
    def __init__(self, repository, embedding_provider=None):
        self.repository = repository
        self.embedding_provider = embedding_provider

    def retrieve(self, request):
        embedding = (
            self.embedding_provider.embed(request.query)
            if self.embedding_provider is not None
            else None
        )
        return self.repository.search(request, embedding)
