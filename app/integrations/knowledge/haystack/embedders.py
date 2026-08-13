"""Haystack dense embedders used by the adapter.

Dense embedding is platform-owned (Ollama ``bge-m3``).  Sparse embedding is a
jieba-tokenized lexical sparse embedder in ``jieba_sparse.py``.
"""

import dataclasses
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from haystack import component
from haystack.dataclasses import Document


def _ollama_embed(endpoint, model, text, timeout):
    request = Request(
        endpoint.rstrip("/") + "/api/embed",
        data=json.dumps({"model": model, "input": text}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
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


@component
class OllamaTextEmbedder:
    """Dense query embedder backed by an Ollama embedding endpoint."""

    def __init__(self, endpoint, model, timeout=30.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout

    @component.output_types(embedding=list[float])
    def run(self, text: str):
        return {"embedding": _ollama_embed(self.endpoint, self.model, text, self.timeout)}


@component
class OllamaDocumentEmbedder:
    """Dense document embedder for the indexing pipeline."""

    def __init__(self, endpoint, model, timeout=30.0):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.timeout = timeout

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]):
        return {
            "documents": [
                dataclasses.replace(
                    document,
                    embedding=_ollama_embed(
                        self.endpoint, self.model, document.content or "", self.timeout
                    ),
                )
                for document in documents
            ]
        }
