"""ReviewInsight job lifecycle manager (Phase 11.3)."""

import uuid

from app.commerce.review_insight.domain import (
    JOB_CANCELLED,
    JOB_CREATED,
    JOB_FAILED,
    JOB_RUNNING,
    JOB_STATUSES,
    JOB_SUCCEEDED,
    ReviewInsightJob,
)
from app.commerce.review_insight.errors import JobNotFoundError


class ReviewInsightJobManager:
    """Owns job creation, lookup, retry, and cancellation.

    Status transitions for a *run* (CREATED -> RUNNING -> PARTIAL/SUCCEEDED/
    FAILED) are driven by the Service, which knows the actual outcome.
    """

    def __init__(self):
        self._jobs = {}

    def create(self, tenant_id, event_id, review_ids, extractor_id,
               extractor_version, trace_id="") -> ReviewInsightJob:
        job = ReviewInsightJob(
            job_id=uuid.uuid4().hex,
            tenant_id=tenant_id,
            event_id=event_id,
            review_ids=tuple(review_ids),
            extractor_id=extractor_id,
            extractor_version=extractor_version,
            status=JOB_CREATED,
            total_count=len(review_ids),
            trace_id=trace_id,
        )
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id) -> ReviewInsightJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise JobNotFoundError(f"job not found: {job_id}")
        return job

    def list_jobs(self) -> list[ReviewInsightJob]:
        return list(self._jobs.values())

    def retry(self, job_id) -> ReviewInsightJob:
        job = self.get(job_id)
        if job.status in (JOB_RUNNING,):
            raise ValueError(f"cannot retry a running job: {job_id}")
        job.retry_count += 1
        job.status = JOB_CREATED
        job.error_summary = ""
        return job

    def cancel(self, job_id) -> ReviewInsightJob:
        job = self.get(job_id)
        if job.status not in (JOB_SUCCEEDED, JOB_FAILED, JOB_CANCELLED):
            job.status = JOB_CANCELLED
        return job

    def set_status(self, job, status):
        if status not in JOB_STATUSES:
            raise ValueError(f"unknown job status: {status}")
        job.status = status
        return job


__all__ = ["ReviewInsightJobManager"]
