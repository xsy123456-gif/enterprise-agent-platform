"""Source document normalization (text cleaning)."""

import re

from app.knowledge.models.document import SourceDocument


class SourceDocumentNormalizer:
    def normalize(self, document: SourceDocument) -> SourceDocument:
        content = document.content or ""
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        content = re.sub(r"[ \t]+\n", "\n", content)
        content = re.sub(r"\n{3,}", "\n\n", content)
        title = (document.title or "").strip()
        return SourceDocument(
            source_system=document.source_system,
            external_id=document.external_id,
            tenant_id=document.tenant_id,
            document_type=document.document_type,
            title=title,
            content=content.strip(),
            source_version=document.source_version,
            source_updated_at=document.source_updated_at,
            language=document.language,
            metadata=dict(document.metadata or {}),
            access_policy=dict(document.access_policy or {}),
        )
