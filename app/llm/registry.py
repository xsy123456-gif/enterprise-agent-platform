"""LLM provider registry — decouples the factory from concrete providers.

Providers self-register; adding a provider only requires a provider module
plus configuration, never a change to the factory or the Planner.
"""


class LLMProviderRegistry:
    def __init__(self):
        self._providers = {}

    def register(self, name, factory_fn):
        if not name:
            raise ValueError("provider name is required")
        if not callable(factory_fn):
            raise TypeError("provider factory must be callable")
        self._providers[name] = factory_fn
        return factory_fn

    def create(self, name, **kwargs):
        factory_fn = self._providers.get(name)
        if factory_fn is None:
            raise ValueError(f"Unsupported LLM provider: {name}")
        return factory_fn(**kwargs)

    def names(self):
        return list(self._providers.keys())


registry = LLMProviderRegistry()
