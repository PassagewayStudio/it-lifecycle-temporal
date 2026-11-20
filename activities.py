"""Activities. Okta activities are real; lock_jamf_device is still a stub.

Keep every activity idempotent: running it twice must be safe, because
Temporal may retry it.
"""
import os

from temporalio import activity
from temporalio.exceptions import ApplicationError

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
    # Permanent and irreversible, so it is off unless you opt in. This stops a
    # typo or a wrong .env from deleting a real account.
    if os.environ.get("OKTA_ALLOW_DELETE") != "true":
        raise ApplicationError(
            "Okta delete is disabled. Set OKTA_ALLOW_DELETE=true in .env to enable it.",
            non_retryable=True,
        )
    activity.logger.info("Deleting Okta user %s", user_email)
    async with okta_client.build_client() as client:
        outcome = await okta_client.delete_user(client, user_email)
    return f"okta-{outcome}:{user_email}"


@activity.defn
async def grant_okta_group_access(user_email: str, group_id: str) -> str:
    activity.logger.info("Adding %s to Okta group %s", user_email, group_id)
    async with okta_client.build_client() as client:
        await okta_client.add_to_group(client, user_email, group_id)
    return f"granted:{user_email}:{group_id}"


@activity.defn
async def revoke_okta_group_access(user_email: str, group_id: str) -> str:
    activity.logger.info("Removing %s from Okta group %s", user_email, group_id)
    async with okta_client.build_client() as client:
        await okta_client.remove_from_group(client, user_email, group_id)
    return f"revoked:{user_email}:{group_id}"
