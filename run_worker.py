import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities import delete_okta_user, lock_jamf_device, suspend_okta_user
from shared import TASK_QUEUE
from workflows import OffboardingWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[OffboardingWorkflow],
        activities=[suspend_okta_user, lock_jamf_device, delete_okta_user],
    )
    print(f"Worker listening on task queue '{TASK_QUEUE}'. Ctrl+C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
