from dataclasses import dataclass, field
from typing import Any


@dataclass
class ApplicationContainer:
    """Explicit ownership boundary for application-wide components.

    Components are deliberately typed by protocol/behavior rather than by a
    runtime backend.  The container is the only object responsible for the
    application lifecycle; domain services remain unaware of the environment.
    """

    runtime: Any = None
    memory: Any = None
    governance: Any = None
    trace: Any = None
    execution: Any = None
    registry: Any = None
    event_bus: Any = None
    audit: Any = None
    planner: Any = None
    supervisor: Any = None
    environment: str = "development"
    metadata: dict = field(default_factory=dict)
    _started: bool = field(default=False, init=False, repr=False)

    def start(self):
        if self._started:
            return self
        runtime = getattr(self.memory, "runtime", None)
        if runtime is not None and hasattr(runtime, "start"):
            runtime.start()
        for component in (self.runtime, self.governance, self.trace, self.execution):
            starter = getattr(component, "start", None)
            if callable(starter):
                starter()
        self._started = True
        return self

    def stop(self, timeout=None):
        errors = []
        for component in (self.runtime, self.governance, self.trace, self.execution):
            stopper = getattr(component, "stop", None)
            if callable(stopper):
                try:
                    stopper(timeout) if timeout is not None else stopper()
                except TypeError:
                    stopper()
                except Exception as error:  # best effort shutdown, report after all closes
                    errors.append(error)
        runtime = getattr(self.memory, "runtime", None)
        if runtime is not None and hasattr(runtime, "stop"):
            try:
                runtime.stop(timeout)
            except Exception as error:
                errors.append(error)
        self._started = False
        if errors:
            raise RuntimeError("application shutdown failed") from errors[0]

    @property
    def started(self):
        return self._started
