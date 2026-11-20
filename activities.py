"""Activities. suspend_okta_user is real; the others are still stubs.

Keep every activity idempotent: running it twice must be safe, because
Temporal may retry it.
"""
from temporalio import activity

import okta_client


@activity.defn
async def suspend_okta_user(user_email: str) -> str:
    activity.logger.info("Suspending Okta user %s", user_email)
    async with okta_client.build_client() as client:
        outcome = await okta_client.suspend_user(client, user_email)
    return f"okta-{outcome}:{user_email}"


@activity.defn
async def lock_jamf_device(device_serial: str) -> str:
    activity.logger.info("Locking Jamf device %s (stub)", device_serial)
    return f"jamf-locked:{device_serial}"


@activity.defn
async def delete_okta_user(user_email: str) -> str:
    activity.logger.info("Deleting Okta user %s (stub)", user_email)
    return f"okta-deleted:{user_email}"
