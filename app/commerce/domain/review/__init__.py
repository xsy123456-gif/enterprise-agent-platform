"""Review domain: Review, ReviewInsight.

``Review`` is a raw business fact; ``ReviewInsight`` is AI-derived evidence.
They are strictly separated: ReviewInsight is regenerable, and raw Reviews are
never rewritten when an extraction model changes.
"""

from dataclasses import dataclass, field
from typing import Any

from app.commerce.domain.base import utc_now


@dataclass(frozen=True)
class Review:
    review_id: str
    tenant_id: str
    store_id: str
    listing_id: str
    platform: str
    external_review_id: str
    rating: float
    listing_item_id: str | None = None
    title: str = ""
    content: str = ""
    language: str = ""
    verified_purchase: bool = False
    review_at: str | None = None
    updated_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict:
        return {
            "review_id": self.review_id,
            "tenant_id": self.tenant_id,
            "store_id": self.store_id,
            "listing_id": self.listing_id,
            "platform": self.platform,
            "external_review_id": self.external_review_id,
            "rating": self.rating,
            "listing_item_id": self.listing_item_id,
            "title": self.title,
            "content": self.content,
            "language": self.language,
            "verified_purchase": self.verified_purchase,
            "review_at": self.review_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Review":
        return cls(
            review_id=data["review_id"],
            tenant_id=data["tenant_id"],
            store_id=data["store_id"],
            listing_id=data["listing_id"],
            platform=data["platform"],
            external_review_id=data["external_review_id"],
            rating=data["rating"],
            listing_item_id=data.get("listing_item_id"),
            title=data.get("title", ""),
            content=data.get("content", ""),
            language=data.get("language", ""),
            verified_purchase=data.get("verified_purchase", False),
            review_at=data.get("review_at"),
            updated_at=data.get("updated_at", utc_now()),
        )


@dataclass(frozen=True)
class ReviewInsight:
    review_insight_id: str
    review_id: str
    sentiment: str = ""
    topics: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    intent: str = ""
    severity: str = ""
    confidence: float | None = None
    model_provider: str = ""
    model_version: str = ""
    extractor_version: str = ""
    generated_at: str = field(default_factory=utc_now)
    supersedes_id: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "topics", tuple(self.topics or ()))
        object.__setattr__(self, "issues", tuple(self.issues or ()))
        object.__setattr__(self, "strengths", tuple(self.strengths or ()))

    def to_dict(self) -> dict:
        return {
            "review_insight_id": self.review_insight_id,
            "review_id": self.review_id,
            "sentiment": self.sentiment,
            "topics": list(self.topics),
            "issues": list(self.issues),
            "strengths": list(self.strengths),
            "intent": self.intent,
            "severity": self.severity,
            "confidence": self.confidence,
            "model_provider": self.model_provider,
            "model_version": self.model_version,
            "extractor_version": self.extractor_version,
            "generated_at": self.generated_at,
            "supersedes_id": self.supersedes_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewInsight":
        return cls(
            review_insight_id=data["review_insight_id"],
            review_id=data["review_id"],
            sentiment=data.get("sentiment", ""),
            topics=tuple(data.get("topics", ())),
            issues=tuple(data.get("issues", ())),
            strengths=tuple(data.get("strengths", ())),
            intent=data.get("intent", ""),
            severity=data.get("severity", ""),
            confidence=data.get("confidence"),
            model_provider=data.get("model_provider", ""),
            model_version=data.get("model_version", ""),
            extractor_version=data.get("extractor_version", ""),
            generated_at=data.get("generated_at", utc_now()),
            supersedes_id=data.get("supersedes_id"),
        )


__all__ = ["Review", "ReviewInsight"]
