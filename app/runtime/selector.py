import os

from app.runtime.ports import GraphRuntime


class RuntimeSelector:
    """Select a GraphRuntime without exposing backend types to Supervisor."""

    def __init__(self, runtimes=None, default_backend="langgraph"):
        self._runtimes = {}
        self.default_backend = default_backend
        for backend_type, runtime in dict(runtimes or {}).items():
            self.register(backend_type, runtime)

    def register(self, backend_type, runtime):
        if not backend_type:
            raise ValueError("backend_type is required")
        if not isinstance(runtime, GraphRuntime):
            raise TypeError("runtime must implement GraphRuntime")
        self._runtimes[backend_type] = runtime
        return runtime

    def select(self, agent=None, version=None, agent_definition=None,
               environment=None, feature_flags=None):
        if (
            isinstance(agent, str)
            and agent in self._runtimes
            and version is None
            and agent_definition is None
            and environment is None
            and feature_flags is None
        ):
            return self._runtimes[agent]
        del agent, version  # Identity is an input for future policy selectors.
        environment = dict(os.environ if environment is None else environment)
        feature_flags = dict(feature_flags or {})
        configured = (
            feature_flags.get("runtime_backend")
            or environment.get("RUNTIME_BACKEND")
            or (
                getattr(agent_definition, "runtime", {}).get("backend")
                if agent_definition is not None else None
            )
            or self.default_backend
        )
        try:
            return self._runtimes[configured]
        except KeyError as error:
            raise KeyError(f"Runtime backend is not registered: {configured}") from error

    def backend_type_for(self, agent_definition=None, environment=None,
                         feature_flags=None):
        environment = dict(os.environ if environment is None else environment)
        feature_flags = dict(feature_flags or {})
        return (
            feature_flags.get("runtime_backend")
            or environment.get("RUNTIME_BACKEND")
            or (
                getattr(agent_definition, "runtime", {}).get("backend")
                if agent_definition is not None else None
            )
            or self.default_backend
        )
