"""Local graph execution policy, separate from Permission/Governance policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GraphExecutionPolicy:
    """Execution shaping only; it grants no Agent, Tool or data permission."""

    max_parallelism: int | None = None
    continue_on_failure: bool = True

    def __post_init__(self):
        if self.max_parallelism is not None and self.max_parallelism <= 0:
            raise ValueError("max_parallelism must be positive")
        if not isinstance(self.continue_on_failure, bool):
            raise TypeError("continue_on_failure must be bool")
