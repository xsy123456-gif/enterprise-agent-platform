"""Provider adapters (Phase 11.4).

The provider architecture is frozen here; real LLM invocation is deferred.  A
ProviderAdapter only maps a provider's raw response into a canonical
``ReviewExtractionResult`` — it never calls the network and never returns a
``ReviewInsight``.  ``ProviderExtractor`` composes an adapter with a
``ProviderClient`` (the deferred LLM seam).
"""

import json
from typing import Protocol

from app.commerce.review_insight.contracts import ReviewExtractorPort
from app.commerce.review_insight.domain import (
    ReviewExtractionBatchResult,
    ReviewExtractionResult,
)
from app.commerce.review_insight.errors import (
    ExtractionError,
    ExtractorUnavailableError,
)


class ProviderAdapter(Protocol):
    provider_name: str
    default_model: str

    def map_response(self, raw, review_id) -> ReviewExtractionResult:
        pass


class ProviderClient(Protocol):
    """Deferred LLM seam — the real HTTP/API call is wired in a later phase."""

    def complete(self, provider_name, review, context=None) -> dict:
        pass


def _parse_model_json(text, provider_name):
    if not isinstance(text, str):
        raise ExtractionError(
            f"{provider_name}: model returned non-string content: "
            f"{type(text).__name__}"
        )
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as error:
        raise ExtractionError(
            f"{provider_name}: model returned invalid JSON: {error}"
        )
    if not isinstance(data, dict):
        raise ExtractionError(
            f"{provider_name}: model returned {type(data).__name__}, expected object"
        )
    return data


def _to_str_tuple(value, provider_name, field):
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, (list, tuple)):
        if not all(isinstance(v, str) for v in value):
            raise ExtractionError(
                f"{provider_name}: {field} must be a list of strings"
            )
        return tuple(value)
    raise ExtractionError(f"{provider_name}: {field} must be a list of strings")


def _build_result(data, review_id, provider_name):
    echoed = data.get("review_id")
    if echoed is not None and echoed != review_id:
        raise ExtractionError(
            f"{provider_name}: review_id mismatch: {echoed!r} != {review_id!r}"
        )

    confidence = data.get("confidence")
    if confidence is not None:
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
            raise ExtractionError(f"{provider_name}: confidence must be a number")
        if not (0.0 <= confidence <= 1.0):
            raise ExtractionError(
                f"{provider_name}: confidence out of range: {confidence!r}"
            )

    sentiment = data.get("sentiment")
    if sentiment is not None and not isinstance(sentiment, str):
        raise ExtractionError(f"{provider_name}: sentiment must be a string")
    intent = data.get("intent")
    if intent is not None and not isinstance(intent, str):
        raise ExtractionError(f"{provider_name}: intent must be a string")
    severity = data.get("severity")
    if severity is not None and not isinstance(severity, str):
        raise ExtractionError(f"{provider_name}: severity must be a string")

    return ReviewExtractionResult(
        review_id=review_id,
        sentiment=sentiment or "",
        topics=_to_str_tuple(data.get("topics"), provider_name, "topics"),
        issues=_to_str_tuple(data.get("issues"), provider_name, "issues"),
        strengths=_to_str_tuple(data.get("strengths"), provider_name, "strengths"),
        intent=intent or "",
        severity=severity or "",
        confidence=confidence,
    )


class BaseProviderAdapter:
    provider_name = ""
    default_model = ""

    def map_response(self, raw, review_id):
        text = self._extract_text(raw)
        data = _parse_model_json(text, self.provider_name)
        return _build_result(data, review_id, self.provider_name)

    def _extract_text(self, raw):
        raise NotImplementedError


class DeepSeekAdapter(BaseProviderAdapter):
    provider_name = "deepseek"
    default_model = "deepseek-chat"

    def _extract_text(self, raw):
        if not isinstance(raw, dict):
            raise ExtractionError("deepseek: response must be an object")
        try:
            return raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ExtractionError(f"deepseek: malformed response: {error}")


class OpenAIAdapter(BaseProviderAdapter):
    provider_name = "openai"
    default_model = "gpt-4o-mini"

    def _extract_text(self, raw):
        if not isinstance(raw, dict):
            raise ExtractionError("openai: response must be an object")
        try:
            return raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ExtractionError(f"openai: malformed response: {error}")


class ClaudeAdapter(BaseProviderAdapter):
    provider_name = "claude"
    default_model = "claude-3-5-sonnet"

    def _extract_text(self, raw):
        if not isinstance(raw, dict):
            raise ExtractionError("claude: response must be an object")
        try:
            return raw["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as error:
            raise ExtractionError(f"claude: malformed response: {error}")


class ProviderExtractor(ReviewExtractorPort):
    """Composes a ProviderClient + ProviderAdapter into ReviewExtractorPort.

    A per-review mapping failure -> ``failed_review_ids`` (PARTIAL); a provider
    outage (``ExtractorUnavailableError`` from the client) propagates (FAILED).
    """

    def __init__(self, adapter, client=None):
        self.adapter = adapter
        self.client = client

    @property
    def provider_name(self):
        return self.adapter.provider_name

    @property
    def default_model(self):
        return self.adapter.default_model

    def extract_batch(self, reviews, context=None):
        if self.client is None:
            raise ExtractorUnavailableError(
                f"{self.adapter.provider_name} client is not configured"
            )
        results = []
        failed = []
        for review in reviews:
            try:
                raw = self.client.complete(
                    self.adapter.provider_name, review, context=context)
                results.append(self.adapter.map_response(raw, review.review_id))
            except ExtractionError:
                failed.append(review.review_id)
        return ReviewExtractionBatchResult(
            results=tuple(results), failed_review_ids=tuple(failed))


__all__ = [
    "ProviderAdapter",
    "ProviderClient",
    "ProviderExtractor",
    "DeepSeekAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
]
