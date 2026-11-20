from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

# Activities and shared code are imported "passed through" so the workflow
# sandbox does not re-import them on every replay.
with workflow.unsafe.imports_passed_through():
    from activities import delete_okta_user, lock_jamf_device, suspend_okta_user
    from shared import OffboardingParams


@workflow.defn
class OffboardingWorkflow:
    def __init__(self) -> None:
        self._status = "started"

    @workflow.run
    async def run(self, params: OffboardingParams) -> dict:
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=5,
        )
        timeout = timedelta(seconds=30)

        self._status = "suspending Okta user"
        okta = await workflow.execute_activity(
            suspend_okta_user,
            params.user_email,
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        self._status = "locking Jamf device"
        jamf = await workflow.execute_activity(
            lock_jamf_device,
            params.device_serial,
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        # Durable timer: it survives worker restarts and server restarts.
        self._status = f"waiting {params.device_return_wait_seconds}s for device return"
        await workflow.sleep(timedelta(seconds=params.device_return_wait_seconds))

        self._status = "deleting Okta user"
        deleted = await workflow.execute_activity(
            delete_okta_user,
            params.user_email,
            start_to_close_timeout=timeout,
            retry_policy=retry,
        )

        self._status = "done"
        return {"okta": okta, "jamf": jamf, "deleted": deleted}

    @workflow.query
    def status(self) -> str:
        """Read-only: what step is this offboarding on? (Handy for the MCP server later.)"""
        return self._status
