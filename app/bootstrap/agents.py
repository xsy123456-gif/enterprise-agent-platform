from app.sources.builtin import BuiltinAgentSource


def register_builtin_agents(registry, llm):
    """Backward-compatible entry point; new code should use BuiltinAgentSource."""
    return BuiltinAgentSource(llm=llm).load(registry)
