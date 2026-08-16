"""Deterministic rule-based extractor (Phase 11.4 v1 baseline).

No LLM, no randomness: keyword + rating heuristics only.  Produces canonical
``ReviewExtractionResult`` so the worker is testable with no external provider.
"""

from app.commerce.review_insight.contracts import ReviewExtractorPort
from app.commerce.review_insight.domain import (
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
)

NEGATIVE_KEYWORDS = (
    "bad", "terrible", "awful", "broken", "defective", "disappointed", "worst",
    "poor", "failed", "fails", "dead", "damaged", "refund", "useless",
)
POSITIVE_KEYWORDS = (
    "great", "good", "excellent", "love", "perfect", "amazing", "best",
    "works", "happy", "recommend", "solid", "awesome",
)

ISSUE_KEYWORDS = {
    "BATTERY_FAILURE": ("battery", "charge", "charging", "drain", "dead"),
    "DEFECTIVE_ITEM": ("broken", "defect", "defective", "damaged", "cracked"),
    "SHIPPING_DELAY": ("shipping", "shipped", "delivery", "delayed", "late"),
    "QUALITY_CONCERN": ("cheap", "flimsy", "quality", "material"),
    "SIZE_FIT": ("size", "fit", "tight", "loose", "small", "large"),
}

STRENGTH_KEYWORDS = {
    "VALUE_FOR_MONEY": ("value", "price", "worth", "affordable", "cheap"),
    "BUILD_QUALITY": ("solid", "sturdy", "durable", "premium", "quality"),
    "EASE_OF_USE": ("easy", "simple", "intuitive", "setup"),
    "PERFORMANCE": ("fast", "powerful", "performance", "smooth"),
}

TOPIC_KEYWORDS = {
    "battery": ("battery", "charge", "charging"),
    "shipping": ("shipping", "delivery", "arrived"),
    "quality": ("quality", "material", "build"),
    "usability": ("easy", "simple", "intuitive", "setup"),
    "size": ("size", "fit", "tight", "loose"),
}


class RuleBasedExtractor(ReviewExtractorPort):
    provider_name = "rule_based"
    version = "1.0"

    def extract_batch(self, reviews, context=None):
        results = [self._extract(review) for review in reviews]
        return ReviewExtractionBatchResult(results=tuple(results))

    def _extract(self, review):
        text = f"{review.title} {review.content}".lower()
        rating = review.rating or 0.0

        negative = any(k in text for k in NEGATIVE_KEYWORDS)
        positive = any(k in text for k in POSITIVE_KEYWORDS)

        if negative and not positive:
            sentiment = "negative"
        elif positive and not negative:
            sentiment = "positive"
        elif rating <= 2:
            sentiment = "negative"
        elif rating == 3:
            sentiment = "neutral"
        else:
            sentiment = "positive"

        issues = tuple(
            code for code, keywords in ISSUE_KEYWORDS.items()
            if any(k in text for k in keywords)
        )
        strengths = tuple(
            code for code, keywords in STRENGTH_KEYWORDS.items()
            if any(k in text for k in keywords)
        )
        topics = tuple(
            topic for topic, keywords in TOPIC_KEYWORDS.items()
            if any(k in text for k in keywords)
        )

        if "?" in (review.content or ""):
            intent = "question"
        elif sentiment == "negative":
            intent = "complaint"
        elif sentiment == "positive":
            intent = "praise"
        else:
            intent = "feedback"

        if issues and rating <= 1:
            severity = "critical"
        elif issues and rating == 2:
            severity = "high"
        elif issues:
            severity = "medium"
        elif sentiment == "negative":
            severity = "low"
        else:
            severity = ""

        confidence = 0.9 if (negative or positive or issues or strengths) else 0.6

        return ReviewExtractionResult(
            review_id=review.review_id,
            sentiment=sentiment,
            topics=topics,
            issues=issues,
            strengths=strengths,
            intent=intent,
            severity=severity,
            confidence=confidence,
        )


__all__ = ["RuleBasedExtractor"]
