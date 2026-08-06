import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.memory.embedding.base import BaseEmbedding, EmbeddingProviderError
from app.memory.embedding.models import EmbeddingResult


class OllamaEmbeddingProvider(BaseEmbedding):
    def __init__(self, endpoint, model, version="latest", timeout=30.0, opener=None):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.version = version
        self.timeout = timeout
        self.opener = opener or urlopen

    def embed(self, text):
        request = Request(
            self.endpoint + "/api/embed",
            data=json.dumps({"model": self.model, "input": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EmbeddingProviderError(
                f"Ollama embedding request failed: {error}"
            ) from error
        embeddings = payload.get("embeddings")
        vector = embeddings[0] if embeddings else payload.get("embedding")
        if not isinstance(vector, list) or not vector:
            raise EmbeddingProviderError("Ollama response does not contain an embedding")
        returned_model = payload.get("model") or self.model
        version = returned_model.rsplit(":", 1)[1] if ":" in returned_model else self.version
        return EmbeddingResult(
            vector=vector, model=returned_model, version=version,
            dimension=len(vector),
        )
