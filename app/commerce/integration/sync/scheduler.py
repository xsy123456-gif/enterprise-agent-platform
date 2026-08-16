"""Sync scheduler (Phase 12.9.6).

Minimal scheduler: holds a set of (SyncDefinition, ConnectorBinding) schedules
and runs them on demand.  Cron/trigger integration is out of scope.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ScheduledSync:
    sync_definition: object
    binding: object
    schedule: str = ""


class SyncScheduler:

    def __init__(self, runtime):
        self.runtime = runtime
        self._schedules = {}

    def register(self, sync_definition, binding, schedule="on_demand"):
        self._schedules[sync_definition.sync_id] = ScheduledSync(
            sync_definition=sync_definition, binding=binding, schedule=schedule,
        )
        return self._schedules[sync_definition.sync_id]

    def run_all(self, trace_id=None):
        results = {}
        for scheduled in self._schedules.values():
            results[scheduled.sync_definition.sync_id] = self.runtime.run(
                scheduled.sync_definition, scheduled.binding, trace_id=trace_id,
            )
        return results

    def run(self, sync_id, trace_id=None):
        scheduled = self._schedules[sync_id]
        return self.runtime.run(scheduled.sync_definition, scheduled.binding,
                                trace_id=trace_id)


__all__ = ["SyncScheduler", "ScheduledSync"]
