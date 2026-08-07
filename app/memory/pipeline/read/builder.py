class ReadPipeline:
    def __init__(self, scope_filter, retriever, pre_ranker, fine_ranker,
                 deduplicator, compressor, context_builder, repository):
        self.scope_filter = scope_filter
        self.retriever = retriever
        self.pre_ranker = pre_ranker
        self.fine_ranker = fine_ranker
        self.deduplicator = deduplicator
        self.compressor = compressor
        self.context_builder = context_builder
        self.repository = repository

    def execute(self, request):
        request = self.scope_filter.authorize(request)
        candidates = self.retriever.retrieve(request)
        candidates = self.pre_ranker.rank(candidates)
        candidates = self.fine_ranker.rank(candidates)
        candidates = self.deduplicator.deduplicate(candidates)[:request.limit]
        summary = self.compressor.compress(candidates, request.query)
        for item, _ in candidates:
            self.repository.record_access(item.id, request)
        return self.context_builder.build(summary, candidates)
