from app.runtime.ports.graph_runtime import GraphRuntime


class CurrentRuntimeAdapter(GraphRuntime):
    """GraphRuntime adapter over the existing RuntimeEngine.

    It deliberately delegates to RuntimeEngine instead of duplicating the
    current AgentExecutionLoop, ToolRunner, Memory, or EventBus behavior.
    """

    def __init__(self, runtime_engine):
        self.runtime_engine = runtime_engine

    def execute(self, graph, input):
        agent_id = getattr(graph, "agent_id", None)
        version = getattr(graph, "version", None)
        if not agent_id or not version:
            raise ValueError("Compiled graph must provide agent_id and version")
        return self.runtime_engine.run(
            input,
            agent_id=agent_id,
            version=version,
        )
