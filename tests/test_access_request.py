"""Access request workflow tests (time-skipping, fake activities, no Okta)."""
import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from access_workflows import AccessRequestWorkflow
from shared import TASK_QUEUE, AccessRequestParams

CALLS: list = []


@activity.defn(name="grant_okta_group_access")
async def fake_grant(user_email: str, group_id: str) -> str:
    CALLS.append(("grant", user_email, group_id))
    return "granted"


@activity.defn(name="revoke_okta_group_access")
async def fake_revoke(user_email: str, group_id: str) -> str:
    CALLS.append(("revoke", user_email, group_id))
    return "revoked"


DAY = 24 * 60 * 60


async def _run(signals, params):
    """Start the workflow, send the given signals, return its result."""
    CALLS.clear()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=TASK_QUEUE,
            workflows=[AccessRequestWorkflow],
            activities=[fake_grant, fake_revoke],
        ):
            handle = await env.client.start_workflow(
                AccessRequestWorkflow.run,
                params,
                id=f"test-{uuid.uuid4()}",
                task_queue=TASK_QUEUE,
            )
            for sig, *args in signals:
                await handle.signal(sig, *args)
            return await handle.result()


@pytest.mark.asyncio
async def test_approved_access_is_granted_then_revoked_after_timer():
    params = AccessRequestParams("jane@example.com", "00g1", duration_seconds=14 * DAY)
    result = await _run([(AccessRequestWorkflow.approve, "manager")], params)
    assert result == {"outcome": "completed", "ended": "expired", "approved_by": "manager"}
    assert [c[0] for c in CALLS] == ["grant", "revoke"]


@pytest.mark.asyncio
async def test_denied_request_never_grants():
    params = AccessRequestParams("jane@example.com", "00g1")
    result = await _run([(AccessRequestWorkflow.deny, "manager")], params)
    assert result["outcome"] == "denied"
    assert CALLS == []


@pytest.mark.asyncio
async def test_unanswered_request_expires_without_granting():
    params = AccessRequestParams("jane@example.com", "00g1", approval_timeout_seconds=3 * DAY)
    result = await _run([], params)
    assert result == {"outcome": "approval-timed-out"}
    assert CALLS == []


@pytest.mark.asyncio
async def test_revoke_now_ends_access_early():
    params = AccessRequestParams("jane@example.com", "00g1", duration_seconds=14 * DAY)
    result = await _run(
        [(AccessRequestWorkflow.approve, "manager"), (AccessRequestWorkflow.revoke_now,)],
        params,
    )
    assert result["ended"] == "revoked-early"
    assert [c[0] for c in CALLS] == ["grant", "revoke"]
