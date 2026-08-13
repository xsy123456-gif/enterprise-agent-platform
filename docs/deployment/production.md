# Production

Start the infrastructure boundary:

```bash
cp .env.example .env
docker compose up -d
APP_ENV=production python -c "from app.composition import create_application; print(create_application('production').health())"
```

If the PostgreSQL (5433), Redis (6379), or Qdrant (6333) ports are already
occupied by running infrastructure containers, reuse them directly instead of
re-running `docker compose up -d`, which would fail with "port already
allocated". The ports configured in `docker-compose.yml` are correct and do
not need to change.

The production composition creates lazy PostgreSQL, Redis, and Qdrant
providers. Health checks open connections and return a per-provider result.
Install the production extra to enable the native LangGraph PostgreSQL
checkpointer:

```bash
python -m pip install -e '.[production]'
```
