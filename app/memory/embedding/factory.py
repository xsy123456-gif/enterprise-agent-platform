from app.memory.embedding.config import EmbeddingConfig
from app.memory.embedding.models import EmbeddingSpace
from app.memory.embedding.providers.ollama import OllamaEmbeddingProvider
from app.memory.embedding.providers.openai import OpenAIEmbeddingProvider
from app.memory.embedding.service import EmbeddingService


def create_embedding_service(expected_dimension, config=None):
    config = config or EmbeddingConfig.from_environment()
    model, version = _model_and_version(config.model, config.version)
    if config.provider == "ollama":
        provider = OllamaEmbeddingProvider(
            endpoint=config.endpoint, model=config.model,
            version=config.version, timeout=config.timeout,
        )
    elif config.provider == "openai":
        provider = OpenAIEmbeddingProvider(
            endpoint=config.endpoint, model=config.model,
            api_key=config.api_key, version=config.version,
            timeout=config.timeout,
        )
    else:
        raise ValueError(f"Unsupported embedding provider: {config.provider}")
    return EmbeddingService(
        provider,
        expected_dimension,
        EmbeddingSpace(config.provider, model, version, expected_dimension),
    )


def _model_and_version(model, configured_version):
    if ":" in model:
        return model.rsplit(":", 1)
    return model, configured_version
