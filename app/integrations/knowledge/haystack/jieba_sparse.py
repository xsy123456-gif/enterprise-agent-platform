"""Jieba-tokenized sparse embedder (Chinese lexical retrieval).

FastEmbed's BM25 uses whitespace tokenization and fails on Chinese (evaluation:
Recall@3 = 0).  This platform-owned component uses jieba word segmentation with
term-frequency weighting, giving a real lexical sparse vector for CJK text.
"""

import hashlib

import jieba
from haystack import component
from haystack.dataclasses import Document, SparseEmbedding

DEFAULT_VOCAB_SIZE = 1_000_000


def _token_counts(text):
    counts = {}
    for token in jieba.cut(text or ""):
        token = token.strip()
        if not token:
            continue
        counts[token] = counts.get(token, 0) + 1.0
    return counts


def _sparse(counts, vocab_size):
    indices = []
    values = []
    total = sum(counts.values()) or 1.0
    for token, count in counts.items():
        index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % vocab_size
        indices.append(index)
        values.append(count / total)
    return SparseEmbedding(indices=indices, values=values)


@component
class JiebaSparseTextEmbedder:
    def __init__(self, vocab_size=DEFAULT_VOCAB_SIZE):
        self.vocab_size = vocab_size

    @component.output_types(sparse_embedding=SparseEmbedding)
    def run(self, text: str):
        return {"sparse_embedding": _sparse(_token_counts(text), self.vocab_size)}


@component
class JiebaSparseDocumentEmbedder:
    def __init__(self, vocab_size=DEFAULT_VOCAB_SIZE):
        self.vocab_size = vocab_size

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]):
        return {
            "documents": [
                Document(
                    id=document.id,
                    content=document.content,
                    meta=document.meta,
                    embedding=document.embedding,
                    score=document.score,
                    sparse_embedding=_sparse(
                        _token_counts(document.content), self.vocab_size
                    ),
                )
                for document in documents
            ]
        }
