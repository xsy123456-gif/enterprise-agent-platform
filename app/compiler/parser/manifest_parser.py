from app.compiler.models.input import CompileInput


class ManifestCompileParser:
    """Adapts the existing validated Manifest output to compiler input.

    YAML parsing deliberately remains owned by ``app.manifest``.  The compiler
    starts from AgentDefinition so all Agent sources share one compiler path.
    """

    def parse(self, agent_definition, capability_catalog, tool_registry,
              policy_registry, compiler_version):
        return CompileInput(
            agent_definition=agent_definition,
            capability_catalog=capability_catalog,
            tool_registry=tool_registry,
            policy_registry=policy_registry,
            compiler_version=compiler_version,
        )
