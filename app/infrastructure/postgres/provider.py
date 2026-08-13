from contextlib import contextmanager


class PostgresProvider:
    """Small psycopg boundary; connections are opened only on use."""

    def __init__(self, url):
        if not url:
            raise ValueError("PostgreSQL URL is required")
        self.url = url

    @contextmanager
    def connection(self):
        try:
            import psycopg
        except ImportError as error:
            raise RuntimeError("psycopg is required for PostgreSQL") from error
        conn = psycopg.connect(self.url)
        try:
            yield conn
        finally:
            conn.close()

    def connection_factory(self):
        return self.connection()

    def health(self):
        try:
            with self.connection() as conn:
                conn.execute("SELECT 1")
            return {"name": "database", "healthy": True}
        except Exception as error:
            return {"name": "database", "healthy": False, "error": str(error)}
