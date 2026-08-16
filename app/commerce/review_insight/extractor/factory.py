"""Extractor factory (Phase 11.4)."""

from dataclasses import dataclass

from app.commerce.review_insight.errors import ExtractionError
from app.commerce.review_insight.extractor.providers import (
    ClaudeAdapter,
    DeepSeekAdapter,
    OpenAIAdapter,
    ProviderExtractor,
)
from app.commerce.review_insight.extractor.rule_based import RuleBasedExtractor


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "rule_based"
    model: str = ""

    def __post_init__(self):
        if not self.provider:
            object.__setattr__(self, "provider", "rule_based")


def build_adapter(provider):
    provider = (provider or "").strip().lower()
    if provider == "deepseek":
        return DeepSeekAdapter()
    if provider == "openai":
        return OpenAIAdapter()
    if provider == "claude":
        return ClaudeAdapter()
    raise ExtractionError(f"unsupported provider: {provider!r}")


def build_extractor(provider_config=None, client=None):
    if provider_config is None:
        return RuleBasedExtractor()
    if isinstance(provider_config, str):
        provider = provider_config
    else:
        provider = getattr(provider_config, "provider", "rule_based")
    provider = (provider or "").strip().lower()
    if provider in ("rule_based", "rule-based", ""):
        return RuleBasedExtractor()
    adapter = build_adapter(provider)
    return ProviderExtractor(adapter, client=client)


__all__ = ["ProviderConfig", "build_adapter", "build_extractor"]
