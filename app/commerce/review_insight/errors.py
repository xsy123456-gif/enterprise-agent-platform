"""ReviewInsight worker errors (Phase 11)."""

from app.commerce.contracts.errors import CommerceError


class ReviewInsightError(CommerceError):
    """Base error for the ReviewInsight worker."""


class ExtractionError(ReviewInsightError):
    """A provider produced an invalid/unmappable extraction result."""


class ExtractorUnavailableError(ReviewInsightError):
    """The configured extractor/provider is unavailable."""


class JobNotFoundError(ReviewInsightError):
    """A ReviewInsightJob was not found."""


__all__ = [
    "ReviewInsightError",
    "ExtractionError",
    "ExtractorUnavailableError",
    "JobNotFoundError",
]
