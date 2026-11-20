"""Time-skipping test: the 14-day wait runs in about a second.

Run from the project root:  python -m pytest -q
(needs: pip install pytest pytest-asyncio)
"""
import uuid

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from activities import delete_okta_user, lock_jamf_device, suspend_okta_user
from shared import TASK_QUEUE, OffboardingParams
from workflows import OffboardingWorkflow


@pytest.mark.asyncio
async def test_offboarding_runs_all_steps_after_timer():
    fourteen_days = 14 * 24 * 60 * 60
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[OffboardingWorkflow],
            activities=[suspend_okta_user, lock_jamf_device, delete_okta_user],
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
