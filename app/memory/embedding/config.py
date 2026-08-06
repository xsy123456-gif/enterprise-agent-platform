import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: str
    model: str
    endpoint: str
    version: str = "latest"
    api_key: str | None = None
    timeout: float = 30.0

    @classmethod
    def from_environment(cls):
        provider = os.getenv("EMBEDDING_PROVIDER")
        model = os.getenv("EMBEDDING_MODEL")
        endpoint = os.getenv("EMBEDDING_ENDPOINT")
        if not all((provider, model, endpoint)):
            raise RuntimeError(
                "EMBEDDING_PROVIDER, EMBEDDING_MODEL and EMBEDDING_ENDPOINT are required"
            )
        return cls(
            provider=provider.strip().lower(), model=model.strip(),
            endpoint=endpoint.strip(),
            version=os.getenv("EMBEDDING_VERSION", "latest").strip(),
            api_key=os.getenv("EMBEDDING_API_KEY"),
            timeout=float(os.getenv("EMBEDDING_TIMEOUT", "30")),
        )
