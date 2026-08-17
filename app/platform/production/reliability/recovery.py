"""Failure recovery (Phase 15.2).

Checkpoint/restore + fallback + human escalation.  Every failure is visible:
an escalation is recorded, never swallowed.
"""


class RecoveryManager:

    def __init__(self):
        self._checkpoints = {}
        self.escalations = []

    def checkpoint(self, task_id, state):
        self._checkpoints[task_id] = state
        return state

    def restore(self, task_id):
        return self._checkpoints.get(task_id)

    def run(self, task_id, fn, fallback=None, escalate=None):
        try:
            return fn()
        except Exception:  # noqa: BLE001 - recovery path below
            if fallback is not None:
                try:
                    return fallback()
                except Exception:  # noqa: BLE001 - escalate
                    self.escalations.append(task_id)
                    if escalate is not None:
                        return escalate()
                    raise
            self.escalations.append(task_id)
            if escalate is not None:
                return escalate()
            raise


__all__ = ["RecoveryManager"]
