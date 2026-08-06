def create_postgres_repository(dsn, initialize=False):
    """Create the production repository without coupling the domain layer to psycopg."""
    try:
        import psycopg
        from pgvector.psycopg import register_vector
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL memory storage requires psycopg and pgvector"
        ) from error

    from app.memory.repository.postgres import PostgresMemoryRepository

    if initialize:
        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")

    def connection_factory():
        connection = psycopg.connect(dsn)
        register_vector(connection)
        return connection

    repository = PostgresMemoryRepository(connection_factory)
    if initialize:
        repository.initialize()
    return repository
