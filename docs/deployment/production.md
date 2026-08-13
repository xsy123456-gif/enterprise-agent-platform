# Production

Start the infrastructure boundary:

```bash
cp .env.example .env
docker compose up -d
APP_ENV=production python -c "from app.composition import create_application; print(create_application('production').health())"
```

The production composition creates lazy PostgreSQL, Redis, and Qdrant
providers. Health checks open connections and return a per-provider result.
Install the production extra to enable the native LangGraph PostgreSQL
checkpointer:

```bash
python -m pip install -e '.[production]'
```
