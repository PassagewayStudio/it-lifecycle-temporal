"""Start an offboarding.  Usage: python run_workflow.py [email] [device_serial] [wait_seconds]"""
import asyncio
import sys

from temporalio.client import Client

from shared import TASK_QUEUE, OffboardingParams
from workflows import OffboardingWorkflow


async def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "jane.doe@example.com"
    serial = sys.argv[2] if len(sys.argv) > 2 else "C02TEST12345"
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    client = await Client.connect("localhost:7233")
    handle = await client.start_workflow(
        OffboardingWorkflow.run,
        OffboardingParams(user_email=email, device_serial=serial, device_return_wait_seconds=wait),
        id=f"offboard-{email}",
        task_queue=TASK_QUEUE,
    )
    print(f"Started workflow id={handle.id}. Open http://localhost:8233 to watch it.")
    result = await handle.result()
    print("Result:", result)


if __name__ == "__main__":
    asyncio.run(main())
