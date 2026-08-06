from abc import ABC, abstractmethod


class AgentSource(ABC):
    """A source of Agent definitions, independent from Registry storage."""

    @abstractmethod
    def load(self, registry):
        """Load Agent definitions into the supplied Registry."""
        pass
