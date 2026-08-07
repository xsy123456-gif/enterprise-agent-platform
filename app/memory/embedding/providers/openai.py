import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.memory.embedding.base import BaseEmbedding, EmbeddingProviderError
from app.memory.embedding.models import EmbeddingResult, EmbeddingSpace


class OpenAIEmbeddingProvider(BaseEmbedding):
    def __init__(self, endpoint, model, api_key, version="latest", timeout=30.0,
                 opener=None):
        if not api_key:
            raise ValueError("EMBEDDING_API_KEY is required for the OpenAI provider")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.version = version
        self.timeout = timeout
        self.opener = opener or urlopen

    def embed(self, text):
        request = Request(
            self.endpoint + "/v1/embeddings",
            data=json.dumps({"model": self.model, "input": text}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise EmbeddingProviderError(
                f"OpenAI-compatible embedding request failed: {error}"
            ) from error
        try:
            vector = payload["data"][0]["embedding"]
        except (KeyError, IndexError, TypeError) as error:
            raise EmbeddingProviderError(
                "OpenAI-compatible response does not contain an embedding"
            ) from error
        returned_model = payload.get("model") or self.model
        return EmbeddingResult(
            vector=vector,
            space=EmbeddingSpace(
                "openai", returned_model, self.version, len(vector)
            ),
        )
