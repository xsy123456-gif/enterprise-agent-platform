"""Adapter health checks (Qdrant connectivity + embedding endpoint)."""

import json
from urllib.request import Request, urlopen

from .config import HaystackKnowledgeConfig
from .document_store import QdrantStoreManager


def check_embedding_endpoint(config: HaystackKnowledgeConfig) -> dict:
    try:
        request = Request(config.ollama_endpoint.rstrip("/") + "/api/tags")
        with urlopen(request, timeout=config.ollama_timeout) as response:
            json.loads(response.read().decode("utf-8"))
        return {"name": "embedding", "healthy": True}
    except Exception as error:
        return {"name": "embedding", "healthy": False, "error": str(error)}


def health(config: HaystackKnowledgeConfig, store_manager: QdrantStoreManager) -> dict:
    return {
        "qdrant": store_manager.health(),
        "embedding": check_embedding_endpoint(config),
    }
