"""Time-skipping workflow test using fake activities (no Okta, no Jamf).

Run from the project root:  python -m pytest -q
"""
import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from shared import TASK_QUEUE, OffboardingParams
from workflows import OffboardingWorkflow


# Fakes registered under the same names the workflow calls.
@activity.defn(name="suspend_okta_user")
async def fake_suspend_okta_user(user_email: str) -> str:
    return f"okta-suspended:{user_email}"


@activity.defn(name="lock_jamf_device")
async def fake_lock_jamf_device(device_serial: str) -> str:
    return f"jamf-locked:{device_serial}"


@activity.defn(name="delete_okta_user")
async def fake_delete_okta_user(user_email: str) -> str:
    return f"okta-deleted:{user_email}"


@pytest.mark.asyncio
async def test_offboarding_runs_all_steps_after_timer():
    fourteen_days = 14 * 24 * 60 * 60
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[OffboardingWorkflow],
            activities=[fake_suspend_okta_user, fake_lock_jamf_device, fake_delete_okta_user],
        ):
            result = await env.client.execute_workflow(
                OffboardingWorkflow.run,
                OffboardingParams("jane.doe@example.com", "C02TEST12345", fourteen_days),
                id=f"test-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
    assert result["okta"] == "okta-suspended:jane.doe@example.com"
    assert result["jamf"] == "jamf-locked:C02TEST12345"
    assert result["deleted"] == "okta-deleted:jane.doe@example.com"
