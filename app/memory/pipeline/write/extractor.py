from dataclasses import dataclass, field
from typing import Any
import json


@dataclass
class MemoryCandidate:
    type: str
    entity_id: str
    attribute: str
    content: Any
    source: str
    confidence: float = 0.8
    business_value: float = 0.5
    stability: float = 0.5
    explicitness: float = 0.5
    future_usefulness: float = 0.5
    frequency: float = 0.0
    recency: float = 1.0
    embedding: list[float] | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def memory_key(self):
        return f"{self.type}:{self.entity_id}:{self.attribute}"


class MemoryExtractor:
    def extract(self, event):
        raise NotImplementedError


class LLMMemoryExtractor(MemoryExtractor):
    def __init__(self, llm):
        self.llm = llm

    def extract(self, event):
        prompt = {
            "task": "Extract durable enterprise memory facts",
            "rules": ["Return JSON array only", "Do not invent facts", "Do not decide persistence"],
            "schema": {"type": "string", "entity_id": "string", "attribute": "string", "content": "any", "confidence": "0..1"},
            "event": {"input": event.input, "output": event.output, "tool_results": event.tool_results},
        }
        response = self.llm.chat([
            {"role": "system", "content": "You are a memory fact extractor, not an Agent."},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ])
        text = response.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]).strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("[")
            if start < 0:
                raise
            data, _ = json.JSONDecoder().raw_decode(text[start:])
        if not isinstance(data, list):
            raise ValueError("Memory extractor must return a JSON array")
        return [MemoryCandidate(source=f"event:{event.event_id}", **item) for item in data]


class StructuredMemoryExtractor(MemoryExtractor):
    """Deterministic adapter for trusted structured candidates and tests."""

    def extract(self, event):
        candidates = event.metadata.get("memory_candidates", [])
        return [MemoryCandidate(source=f"event:{event.event_id}", **item) for item in candidates]
