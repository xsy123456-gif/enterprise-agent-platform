"""Workflow run repository port (Phase 18.10).

``WorkflowRun`` is durable business state: a suspended run (WAITING /
WAITING_APPROVAL) must survive a restart.  The ``WorkflowEngine`` owns
execution semantics; the repository only stores/retrieves run state.
"""

from abc import ABC, abstractmethod


class WorkflowRunRepository(ABC):
    @abstractmethod
    def save(self, run):
        pass

    @abstractmethod
    def get(self, run_id):
        pass


class InMemoryWorkflowRunRepository(WorkflowRunRepository):

    def __init__(self):
        self._runs = {}

    def save(self, run):
        self._runs[run.run_id] = run
        return run

    def get(self, run_id):
        return self._runs.get(run_id)


__all__ = ["WorkflowRunRepository", "InMemoryWorkflowRunRepository"]
