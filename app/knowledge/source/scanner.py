"""Source directory scanner.

Discovers enterprise knowledge files under a root directory, reads sidecar
metadata, and computes checksums so add/modify/delete can be detected.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

from app.knowledge.source.models import KnowledgeSourceDocument

# Directory name -> document_type.  The directory layout is the source of
# truth for document classification.
DIR_TO_TYPE = {
    "products": "product_knowledge",
    "faq": "faq",
    "policies": "policy",
    "operations": "sop",
    "stores": "internal_policy",
    "management": "management_policy",
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}

_META_REQUIRED = {"tenant_id", "security_level", "knowledge_scope"}


def _checksum(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iso(timestamp):
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


class KnowledgeSourceScanner:
    def __init__(self, root: str):
        if not root:
            raise ValueError("scanner root is required")
        self.root = root

    def scan(self) -> list[KnowledgeSourceDocument]:
        documents = []
        if not os.path.isdir(self.root):
            return documents
        for directory in sorted(os.listdir(self.root)):
            dir_path = os.path.join(self.root, directory)
            if not os.path.isdir(dir_path):
                continue
            document_type = DIR_TO_TYPE.get(directory)
            if document_type is None:
                continue
            for file_name in sorted(os.listdir(dir_path)):
                if file_name.startswith("."):
                    continue
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                file_path = os.path.join(dir_path, file_name)
                relative = os.path.relpath(file_path, self.root)
                metadata = self._load_metadata(file_path, document_type)
                stat = os.stat(file_path)
                documents.append(
                    KnowledgeSourceDocument(
                        source_id=relative,
                        file_path=file_path,
                        file_name=file_name,
                        file_type=ext.lstrip("."),
                        document_type=document_type,
                        tenant_id=metadata["tenant_id"],
                        metadata=metadata,
                        created_time=_iso(stat.st_ctime),
                        modified_time=_iso(stat.st_mtime),
                        checksum=_checksum(file_path),
                    )
                )
        return documents

    def _load_metadata(self, file_path: str, document_type: str) -> dict:
        sidecar = file_path + ".meta.json"
        if os.path.exists(sidecar):
            with open(sidecar, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        else:
            data = {}
        merged = {
            "tenant_id": data.get("tenant_id", "default"),
            "document_type": data.get("document_type", document_type),
            "security_level": data.get("security_level", "public"),
            "knowledge_scope": data.get(
                "knowledge_scope", document_type
            ),
            "region": data.get("region"),
            "store_id": data.get("store_id"),
        }
        for key in _META_REQUIRED:
            if not merged.get(key):
                raise ValueError(
                    f"source metadata missing required field '{key}': {file_path}"
                )
        return merged
