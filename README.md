# Enterprise Agent Platform

## Memory database

The production Memory Engine requires PostgreSQL 16 or newer with pgvector.
Configure `MEMORY_DATABASE_URL`, `MEMORY_DATABASE_INITIALIZE`, and
`MEMORY_EMBEDDING_DIMENSION` as shown in `.env.example`.

`MEMORY_DATABASE_INITIALIZE=true` enables idempotent schema creation and
startup validation. The embedding dimension must match the selected embedding
provider; startup fails on a mismatch instead of creating an invalid vector
index.

Run the database integration suite against a dedicated database:

```bash
MEMORY_TEST_DATABASE_URL=postgresql://user:password@localhost:5433/agentdb \
python -m unittest tests.test_memory_postgres -v
```
