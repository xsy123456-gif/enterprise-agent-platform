# Testing

Install the project and test extras, then run the isolated suite:

```bash
python -m pip install -e '.[test]'
python -m pytest -q
```

PostgreSQL integration tests run when `MEMORY_TEST_DATABASE_URL` is configured;
otherwise they are explicitly skipped.
