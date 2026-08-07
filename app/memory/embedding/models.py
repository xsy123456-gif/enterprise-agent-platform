import hashlib
import json
from dataclasses import dataclass, field


@dataclass(frozen=True)
class EmbeddingSpace:
    provider: str
    model: str
    version: str
    dimension: int
    space_id: str = field(init=False)

    def __post_init__(self):
        for field_name in ("provider", "model", "version"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Embedding {field_name} must be a non-empty string")
            object.__setattr__(self, field_name, value.strip())
        if not isinstance(self.dimension, int) or self.dimension < 1:
            raise ValueError("Embedding dimension must be a positive integer")
        canonical = json.dumps(
            {
                "provider": self.provider,
                "model": self.model,
                "version": self.version,
                "dimension": self.dimension,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        object.__setattr__(
            self, "space_id", hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        )


@dataclass(frozen=True)
class EmbeddingResult:
    vector: list[float]
    space: EmbeddingSpace

    @property
    def provider(self):
        return self.space.provider

    @property
    def model(self):
        return self.space.model

    @property
    def version(self):
        return self.space.version

    @property
    def dimension(self):
        return self.space.dimension

    @property
    def space_id(self):
        return self.space.space_id
