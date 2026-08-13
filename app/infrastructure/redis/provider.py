class RedisProvider:
    """Lazy Redis boundary reserved for cache, events, and distributed locks."""

    def __init__(self, url="redis://localhost:6379/0"):
        self.url = url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                import redis
            except ImportError as error:
                raise RuntimeError("redis package is required for Redis") from error
            self._client = redis.Redis.from_url(self.url, decode_responses=True)
        return self._client

    def health(self):
        try:
            healthy = bool(self.client.ping())
            return {"name": "redis", "healthy": healthy}
        except Exception as error:
            return {"name": "redis", "healthy": False, "error": str(error)}
