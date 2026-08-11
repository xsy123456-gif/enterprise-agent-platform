from dataclasses import replace
from threading import RLock

from .models import AgentLifecycleRecord, AgentLifecycleState, utc_now


class AgentLifecycleManager:
    """Control-plane lifecycle gate, separate from artifact lifecycle state."""

    TRANSITIONS = {
        AgentLifecycleState.CREATED: {AgentLifecycleState.REGISTERED},
        AgentLifecycleState.REGISTERED: {AgentLifecycleState.VALIDATED},
        AgentLifecycleState.VALIDATED: {AgentLifecycleState.ACTIVE},
        AgentLifecycleState.ACTIVE: {
            AgentLifecycleState.SUSPENDED,
            AgentLifecycleState.DEPRECATED,
        },
        AgentLifecycleState.SUSPENDED: {
            AgentLifecycleState.ACTIVE,
            AgentLifecycleState.DEPRECATED,
        },
        AgentLifecycleState.DEPRECATED: {AgentLifecycleState.ARCHIVED},
        AgentLifecycleState.ARCHIVED: set(),
    }

    def __init__(self, on_change=None):
        self._records: dict[str, AgentLifecycleRecord] = {}
        self._lock = RLock()
        self._on_change = on_change

    def create(self, agent_id: str) -> AgentLifecycleRecord:
        record = AgentLifecycleRecord(agent_id=agent_id)
        with self._lock:
            if agent_id in self._records:
                raise ValueError(f"Agent lifecycle already exists: {agent_id}")
            self._records[agent_id] = record
        self._notify(None, record)
        return record

    def get(self, agent_id: str) -> AgentLifecycleRecord:
        try:
            return self._records[agent_id]
        except KeyError as error:
            raise KeyError(f"Agent lifecycle not found: {agent_id}") from error

    def transition(self, agent_id: str, target) -> AgentLifecycleRecord:
        target = AgentLifecycleState(target)
        with self._lock:
            current = self.get(agent_id)
            if target not in self.TRANSITIONS[current.state]:
                raise ValueError(
                    f"Invalid Agent lifecycle transition: "
                    f"{current.state.value} -> {target.value}"
                )
            updated = replace(current, state=target, updated_at=utc_now())
            self._records[agent_id] = updated
        self._notify(current, updated)
        return updated

    def assert_new_execution_allowed(self, agent_id: str) -> None:
        state = self.get(agent_id).state
        if state is not AgentLifecycleState.ACTIVE:
            raise PermissionError(
                f"New execution is forbidden for Agent state: {state.value}"
            )

    def assert_resume_allowed(self, agent_id: str) -> None:
        state = self.get(agent_id).state
        if state not in {
            AgentLifecycleState.ACTIVE,
            AgentLifecycleState.SUSPENDED,
            AgentLifecycleState.DEPRECATED,
        }:
            raise PermissionError(
                f"Execution resume is forbidden for Agent state: {state.value}"
            )

    def assert_new_binding_allowed(self, agent_id: str) -> None:
        state = self.get(agent_id).state
        if state is not AgentLifecycleState.ACTIVE:
            raise PermissionError(
                f"New binding is forbidden for Agent state: {state.value}"
            )

    def _notify(self, previous, current):
        if self._on_change is not None:
            self._on_change(previous, current)
