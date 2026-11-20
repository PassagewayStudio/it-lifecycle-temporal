"""Stub activities. Each one only logs and returns a result for now.

Later these become real API calls (Okta, Jamf). Keep every activity
idempotent: running it twice must be safe, because Temporal may retry it.
"""
from temporalio import activity


@activity.defn
async def suspend_okta_user(user_email: str) -> str:
    activity.logger.info("Suspending Okta user %s (stub)", user_email)
    return f"okta-suspended:{user_email}"


@activity.defn
async def lock_jamf_device(device_serial: str) -> str:
    activity.logger.info("Locking Jamf device %s (stub)", device_serial)
    return f"jamf-locked:{device_serial}"


@activity.defn
async def delete_okta_user(user_email: str) -> str:
    activity.logger.info("Deleting Okta user %s (stub)", user_email)
    return f"okta-deleted:{user_email}"
