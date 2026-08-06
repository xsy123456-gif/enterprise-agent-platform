class ResultAggregator:
    """Builds deterministic collaboration context from completed step results."""

    def execution_context(self, plan, state):
        capabilities = {step.step_id: step.capability for step in plan.steps}
        return {
            item.step_id: {
                "capability": capabilities[item.step_id],
                "agent_id": item.agent_id,
                "result": item.result,
            }
            for item in state.steps
            if item.status == "completed"
        }

    def dependency_context(self, step, plan, state):
        context = self.execution_context(plan, state)
        return {dependency: context[dependency] for dependency in step.dependencies if dependency in context}

    def final_output(self, plan, state):
        context = self.execution_context(plan, state)
        depended_on = {dependency for step in plan.steps for dependency in step.dependencies}
        terminal_ids = [step.step_id for step in plan.steps if step.step_id not in depended_on]
        outputs = [context[step_id]["result"] for step_id in terminal_ids if step_id in context]
        if len(outputs) == 1:
            return outputs[0]
        return context
