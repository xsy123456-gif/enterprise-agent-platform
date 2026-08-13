"""Knowledge source document model (discovery metadata, not content)."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class KnowledgeSourceDocument:
    """Metadata describing a discovered enterprise knowledge file.

    Carries identity + ACL metadata; the file content is read separately by
    ``read_document``.
    """

    source_id: str
    file_path: str
    file_name: str
    file_type: str  # "pdf" | "docx" | "txt"
    document_type: str
    tenant_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_time: str = ""
    modified_time: str = ""
    checksum: str = ""
