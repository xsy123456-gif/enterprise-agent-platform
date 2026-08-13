"""Platform-neutral mapping between Haystack Documents and RetrievalHit."""

from app.knowledge.ports.retriever import RetrievalHit


def document_to_hit(document) -> RetrievalHit:
    meta = dict(getattr(document, "meta", None) or {})
    return RetrievalHit(
        chunk_id=document.id,
        document_id=meta.get("document_id", ""),
        content=document.content or "",
        score=float(document.score or 0.0),
        metadata=meta,
    )
