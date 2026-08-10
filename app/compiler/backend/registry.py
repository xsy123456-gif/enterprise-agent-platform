from app.compiler.backend.base import BackendCompiler


class BackendCompilerRegistry:
    def __init__(self):
        self._compilers = {}

    def register(self, compiler: BackendCompiler):
        backend_type = getattr(compiler, "backend_type", None)
        if not backend_type:
            raise ValueError("Backend compiler must declare backend_type")
        if backend_type in self._compilers:
            raise ValueError(f"Backend compiler already registered: {backend_type}")
        self._compilers[backend_type] = compiler
        return compiler

    def get(self, backend_type):
        try:
            return self._compilers[backend_type]
        except KeyError as error:
            raise KeyError(f"Backend compiler not found: {backend_type}") from error

    def list_backends(self):
        return sorted(self._compilers)
