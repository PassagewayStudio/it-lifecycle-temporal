import asyncio

from dotenv import load_dotenv
from temporalio.client import Client
from temporalio.worker import Worker

from access_workflows import AccessRequestWorkflow
from activities import (
    delete_okta_user,
    grant_okta_group_access,
    lock_jamf_device,
    revoke_okta_group_access,
    suspend_okta_user,
)
from shared import TASK_QUEUE
from workflows import OffboardingWorkflow


async def main() -> None:
    load_dotenv()  # reads OKTA_* from .env (never commit that file)
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[OffboardingWorkflow, AccessRequestWorkflow],
        activities=[
            suspend_okta_user,
            lock_jamf_device,
            delete_okta_user,
            grant_okta_group_access,
            revoke_okta_group_access,
        ],
    )
    print(f"Worker listening on task queue '{TASK_QUEUE}'. Ctrl+C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
