"""Pure retry decisions; execution remains in RecoveryManager."""

from app.runtime.recovery.models import RecoveryAction, RetryDecision


class RetryManager:
    def decide(self, failure, completed_attempts, policy):
        retry_number = len(completed_attempts)
        can_retry = (
            failure.retryable
            and failure.failure_type in policy.retryable_failures
            and retry_number < policy.max_attempts
        )
        if can_retry:
            return RetryDecision(
                action=RecoveryAction.RETRY,
                retry_number=retry_number,
                delay_seconds=policy.delay_for(retry_number),
                reason=f"retryable {failure.failure_type.value} failure",
            )
        return RetryDecision(
            action=policy.fallback_strategy,
            retry_number=retry_number,
            reason="retry exhausted or failure is not retryable",
        )
