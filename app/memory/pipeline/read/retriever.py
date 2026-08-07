class MemoryRetriever:
    def __init__(self, repository, query_analyzer, embedding_service, candidate_fusion):
        self.repository = repository
        self.query_analyzer = query_analyzer
        self.embedding_service = embedding_service
        self.candidate_fusion = candidate_fusion

    def retrieve(self, request):
        analysis = self.query_analyzer.analyze(request.query)
        sql_candidates = self.repository.search_sql(request, analysis.keywords)
        vector_candidates = []
        if analysis.semantic_required:
            query_embedding = self.embedding_service.embed(request.query)
            vector_candidates = self.repository.search_vector(
                request, query_embedding.vector, query_embedding.space_id
            )
        return self.candidate_fusion.fuse(sql_candidates, vector_candidates)
