# Development

Use the in-memory checkpoint and repository providers for fast local work:

```bash
APP_ENV=development .venv/bin/python -m app.main
```

Copy `.env.example` to `.env` and provide an LLM key only when exercising the
LLM path. Development does not require Docker services.
