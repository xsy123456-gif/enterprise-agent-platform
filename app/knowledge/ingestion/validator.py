"""Source document validation and sensitive-field rejection."""

from app.knowledge.errors import KnowledgeInvalidRequestError
from app.knowledge.models.document import SourceDocument

SENSITIVE_KEYS = {"password", "api_key", "token", "secret", "credential", "authorization"}


class SourceDocumentValidator:
    def validate(self, document: SourceDocument) -> None:
        if not isinstance(document, SourceDocument):
            raise KnowledgeInvalidRequestError("expected SourceDocument")
        for name in ("source_system", "external_id", "tenant_id", "document_type", "title", "content"):
            value = getattr(document, name, None)
            if not isinstance(value, str) or not value.strip():
                raise KnowledgeInvalidRequestError(f"{name} is required")
        self._reject_sensitive(document.metadata, "metadata")
        self._reject_sensitive(document.access_policy, "access_policy")

    def _reject_sensitive(self, value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if str(key).lower() in SENSITIVE_KEYS:
                    raise KnowledgeInvalidRequestError(
                        f"sensitive field is forbidden in {path}: {key}"
                    )
                self._reject_sensitive(item, f"{path}.{key}")
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                self._reject_sensitive(item, f"{path}[{index}]")
