"""Time-boxed access request: request -> approval (signal) -> grant -> auto-revoke."""
import asyncio
from datetime import timedelta
from typing import Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import grant_okta_group_access, revoke_okta_group_access
    from shared import AccessRequestParams


@workflow.defn
class AccessRequestWorkflow:
    def __init__(self) -> None:
        self._status = "waiting for approval"
        self._decision: Optional[str] = None  # "approved" or "denied"
        self._decided_by: Optional[str] = None
        self._revoke_now = False

    @workflow.signal
    def approve(self, approver: str) -> None:
        if self._decision is None:  # first decision wins
            self._decision, self._decided_by = "approved", approver

    @workflow.signal
    def deny(self, approver: str) -> None:
        if self._decision is None:
            self._decision, self._decided_by = "denied", approver

    @workflow.signal
    def revoke_now(self) -> None:
        """Ends the access early (for example, the person finished the task)."""
        self._revoke_now = True

    @workflow.query
    def status(self) -> str:
        return self._status

    @workflow.run
    async def run(self, params: AccessRequestParams) -> dict:
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=5,
        )
        timeout = timedelta(seconds=30)

        # 1. Wait for a decision, but not forever.
        try:
            await workflow.wait_condition(
                lambda: self._decision is not None,
                timeout=timedelta(seconds=params.approval_timeout_seconds),
            )
        except asyncio.TimeoutError:
            self._status = "expired: nobody decided in time"
            return {"outcome": "approval-timed-out"}

        if self._decision == "denied":
            self._status = f"denied by {self._decided_by}"
            return {"outcome": "denied", "by": self._decided_by}

        # 2. Grant access.
        await workflow.execute_activity(
            grant_okta_group_access,
            args=[params.user_email, params.group_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        self._status = f"access granted (approved by {self._decided_by})"

        # 3. Durable timer: access lasts N seconds unless revoked early.
        try:
            await workflow.wait_condition(
                lambda: self._revoke_now,
                timeout=timedelta(seconds=params.duration_seconds),
            )
            ended = "revoked-early"
        except asyncio.TimeoutError:
            ended = "expired"

        # 4. Always take the access away again.
        await workflow.execute_activity(
            revoke_okta_group_access,
            args=[params.user_email, params.group_id],
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )
        self._status = f"access removed ({ended})"
        return {"outcome": "completed", "ended": ended, "approved_by": self._decided_by}
