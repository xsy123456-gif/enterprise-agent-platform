"""ReviewInsight extractor package (Phase 11.4).

Provider architecture is frozen; real LLM invocation is deferred.
"""

from app.commerce.review_insight.extractor.factory import (
    ProviderConfig,
    build_adapter,
    build_extractor,
)
from app.commerce.review_insight.extractor.providers import (
    ClaudeAdapter,
    DeepSeekAdapter,
    OpenAIAdapter,
    ProviderAdapter,
    ProviderClient,
    ProviderExtractor,
)
from app.commerce.review_insight.extractor.rule_based import RuleBasedExtractor

__all__ = [
    "RuleBasedExtractor",
    "ProviderAdapter",
    "ProviderClient",
    "ProviderExtractor",
    "DeepSeekAdapter",
    "OpenAIAdapter",
    "ClaudeAdapter",
    "ProviderConfig",
    "build_adapter",
    "build_extractor",
]
