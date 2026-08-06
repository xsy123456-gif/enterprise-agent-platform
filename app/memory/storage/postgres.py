def create_postgres_repository(dsn, embedding_dimension, initialize=False):
    """Create the production repository without coupling the domain layer to psycopg."""
    try:
        import psycopg
        from pgvector.psycopg import register_vector
    except ImportError as error:
        raise RuntimeError(
            "PostgreSQL memory storage requires psycopg and pgvector"
        ) from error

    from app.memory.repository.postgres import PostgresMemoryRepository

    def connection_factory(register_types=True):
        connection = psycopg.connect(dsn)
        if register_types:
            try:
                register_vector(connection)
            except psycopg.ProgrammingError as error:
                connection.close()
                raise RuntimeError(
                    "pgvector is not initialized; set MEMORY_DATABASE_INITIALIZE=true"
                ) from error
        return connection

    repository = PostgresMemoryRepository(connection_factory, embedding_dimension)
    repository.healthcheck()
    if initialize:
        repository.initialize()
    else:
        repository.validate_schema()
    return repository
