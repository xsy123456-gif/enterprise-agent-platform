from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ExecutionJob:
    step_id: str
    execute: Callable[[], Any]


@dataclass
class ExecutionJobResult:
    step_id: str
    output: Any = None
    error: Exception | None = None


class ParallelTaskScheduler:
    """Executes a ready-step batch locally without selecting Agents."""

    def __init__(self, max_workers=8):
        self.max_workers = max_workers

    def create_jobs(self, ready_steps, job_factory):
        return [ExecutionJob(step.step_id, job_factory(step)) for step in ready_steps]

    def execute(self, jobs):
        if not jobs:
            return []
        workers = min(self.max_workers, len(jobs))
        results = []
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="agent-step") as pool:
            futures = {pool.submit(job.execute): job.step_id for job in jobs}
            for future in as_completed(futures):
                step_id = futures[future]
                try:
                    results.append(ExecutionJobResult(step_id, output=future.result()))
                except Exception as error:
                    results.append(ExecutionJobResult(step_id, error=error))
        return results
