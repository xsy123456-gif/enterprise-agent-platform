"""Self-built Haystack embedders (platform-owned components, not forks).

Haystack 3.0 does not ship an Ollama embedder, so we provide our own components
per the "build a Haystack Component" principle.  They are plain Haystack
components and can be placed into a query pipeline.
"""

import hashlib
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from haystack import component
from haystack.dataclasses import SparseEmbedding


@component
class OllamaTextEmbedder:
    """Dense query embedder backed by an Ollama embedding endpoint."""

    def __init__(self, endpoint, model, timeout=30.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout

    @component.output_types(embedding=list[float])
    def run(self, text: str):
        vector = self._embed(text)
        return {"embedding": vector}

    def _embed(self, text):
        request = Request(
            self.endpoint + "/api/embed",
            data=json.dumps({"model": self.model, "input": text}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            from app.knowledge.errors import KnowledgeEmbeddingError

            raise KnowledgeEmbeddingError(
                f"ollama embedding request failed: {error}"
            ) from error
        embeddings = payload.get("embeddings")
        vector = embeddings[0] if embeddings else payload.get("embedding")
        if not isinstance(vector, list) or not vector:
            from app.knowledge.errors import KnowledgeEmbeddingError

            raise KnowledgeEmbeddingError("ollama returned no embedding")
        return list(vector)


_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text):
    return [t for t in _TOKEN_RE.split((text or "").lower()) if t]


@component
class HashSparseTextEmbedder:
    """Minimal hash-token sparse embedder (BM25-grade term weighting later)."""

    def __init__(self, vocab_size=10000):
        if vocab_size <= 0:
            raise ValueError("vocab_size must be positive")
        self.vocab_size = vocab_size

    @component.output_types(sparse_embedding=SparseEmbedding)
    def run(self, text: str):
        counts = {}
        for token in _tokenize(text):
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % self.vocab_size
            counts[index] = counts.get(index, 0) + 1.0
        indices = sorted(counts)
        total = sum(counts.values()) or 1.0
        values = [counts[index] / total for index in indices]
        return {"sparse_embedding": SparseEmbedding(indices=indices, values=values)}
