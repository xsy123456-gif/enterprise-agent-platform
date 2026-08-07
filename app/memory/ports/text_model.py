from typing import Protocol


class MemoryTextModel(Protocol):
    """Minimal text-model port used by Memory extraction and compression."""

    def chat(self, messages: list[dict]) -> str:
        ...
