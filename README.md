# Enterprise Agent Platform

## Memory database

The production Memory Engine requires PostgreSQL 16 or newer with pgvector.
Configure `MEMORY_DATABASE_URL`, `MEMORY_DATABASE_INITIALIZE`, and
`MEMORY_EMBEDDING_DIMENSION` as shown in `.env.example`.

`MEMORY_DATABASE_INITIALIZE=true` enables idempotent schema creation and
startup validation. The embedding dimension must match the selected embedding
provider; startup fails on a mismatch instead of creating an invalid vector
index.

Semantic Memory uses a provider-isolated embedding service. The current setup
expects BGE-M3 to run in Windows Ollama and calls it over HTTP; the WSL runtime
does not load model weights. Configure `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`,
`EMBEDDING_ENDPOINT`, and `EMBEDDING_VERSION` in `.env`.

To verify the real provider connection explicitly:

```bash
EMBEDDING_INTEGRATION_TEST=true \
python -m unittest tests.memory.test_embedding.OllamaEmbeddingIntegrationTest -v
```

Run the database integration suite against a dedicated database:

```bash
MEMORY_TEST_DATABASE_URL=postgresql://user:password@localhost:5433/agentdb \
python -m unittest tests.memory.test_postgres -v
```
