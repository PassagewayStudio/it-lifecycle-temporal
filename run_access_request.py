"""Drive an access request from the command line.

  python run_access_request.py request <email> <okta_group_id> [duration_s]
  python run_access_request.py approve <email> [approver]
  python run_access_request.py deny <email> [approver]
  python run_access_request.py revoke <email>
  python run_access_request.py status <email>
  python run_access_request.py result <email>
"""
import asyncio
import sys

from temporalio.client import Client

from access_workflows import AccessRequestWorkflow
from shared import TASK_QUEUE, AccessRequestParams


async def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, email = sys.argv[1], sys.argv[2]
    wf_id = f"access-{email}"
    client = await Client.connect("localhost:7233")

    if cmd == "request":
        group_id = sys.argv[3]
        duration = int(sys.argv[4]) if len(sys.argv) > 4 else 120
        handle = await client.start_workflow(
            AccessRequestWorkflow.run,
            AccessRequestParams(email, group_id, duration_seconds=duration),
            id=wf_id,
            task_queue=TASK_QUEUE,
        )
        print(f"Requested. Workflow id={handle.id}. Waiting for approval.")
        return

    handle = client.get_workflow_handle(wf_id)
    if cmd == "approve":
        await handle.signal(AccessRequestWorkflow.approve, sys.argv[3] if len(sys.argv) > 3 else "manager")
    elif cmd == "deny":
        await handle.signal(AccessRequestWorkflow.deny, sys.argv[3] if len(sys.argv) > 3 else "manager")
    elif cmd == "revoke":
        await handle.signal(AccessRequestWorkflow.revoke_now)
    elif cmd == "status":
        print(await handle.query(AccessRequestWorkflow.status))
    elif cmd == "result":
        print(await handle.result())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    asyncio.run(main())
