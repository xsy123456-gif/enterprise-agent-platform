from app.compiler.ir.builder import AgentGraphIRBuilder
from app.compiler.parser.manifest_parser import ManifestCompileParser
from app.compiler.validator.compiler_validator import CompilerValidator


class GraphCompiler:
    """Stable compiler facade: parse → validate → normalize → build IR."""

    def __init__(self, parser=None, validator=None, builder=None, compiler_version="v0.8.0"):
        self.parser = parser or ManifestCompileParser()
        self.validator = validator or CompilerValidator()
        self.builder = builder or AgentGraphIRBuilder()
        self.compiler_version = compiler_version

    def compile(self, agent_definition, capability_catalog, tool_registry, policy_registry):
        compile_input = self.parser.parse(
            agent_definition, capability_catalog, tool_registry, policy_registry,
            self.compiler_version,
        )
        self.validator.validate(compile_input)
        return self.builder.build(self._normalize(compile_input))

    @staticmethod
    def _normalize(compile_input):
        # Definitions are already manifest-normalized.  This explicit stage is
        # retained as a stable extension point for future compiler versions.
        return compile_input
