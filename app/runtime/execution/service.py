class ExecutionService:
    """Application-facing facade over ExecutionManager."""

    def __init__(self, manager):
        self.manager = manager

    def create(self, state, artifact):
        return self.manager.create(state, artifact)

    def resume_execution(self, execution_id, approval_result, runner):
        return self.manager.resume(execution_id, approval_result, runner)
