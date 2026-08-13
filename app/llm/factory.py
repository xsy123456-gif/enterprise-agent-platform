"""LLM factory — selects a provider from the registry by configuration."""

from app.llm.config import LLMConfig
from app.llm.registry import registry

# Importing the providers package triggers provider self-registration.
import app.llm.providers  # noqa: F401


def create_llm(provider=None, **kwargs):
    """Create an LLM for the configured (or explicitly named) provider."""
    name = provider or LLMConfig.DEFAULT_PROVIDER
    return registry.create(name, **kwargs)
