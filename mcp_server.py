"""Read-only MCP server for the it-lifecycle-temporal workflows.

Lets an AI assistant answer "what step is this offboarding on?" and "why is it
stuck?". It only reads from Temporal. It has NO tools that signal, terminate or
start workflows, and it never touches Okta, so it needs no Okta token.

Run it over stdio:  python mcp_server.py
Optional env var:   TEMPORAL_ADDRESS (default localhost:7233)
"""
import asyncio
import os

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations
from temporalio.client import Client

from diagnose import PendingActivity, hints_for

mcp = MCPServer("it-lifecycle")
READ_ONLY = ToolAnnotations(readOnlyHint=True)

QUERY_TIMEOUT_SECONDS = 5
ALLOWED_STATUSES = {"Running", "Completed", "Failed", "Terminated", "Canceled", "TimedOut"}


async def _client() -> Client:
    return await Client.connect(os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"))


async def _step(handle) -> str | None:
    """Ask the workflow which step it is on. None means no answer (worker down?)."""
    try:
        return await asyncio.wait_for(handle.query("status"), QUERY_TIMEOUT_SECONDS)
    except Exception:
        return None


@mcp.tool(annotations=READ_ONLY)
async def list_workflows(status: str = "Running", limit: int = 20) -> list[dict]:
    """List offboarding and access-request workflows by status.

    status is one of: Running, Completed, Failed, Terminated, Canceled, TimedOut.
    """
    if status not in ALLOWED_STATUSES:
        return [{"error": f"status must be one of {sorted(ALLOWED_STATUSES)}"}]
    client = await _client()
    results: list[dict] = []
    async for wf in client.list_workflows(f'ExecutionStatus="{status}"'):
        results.append(
            {
                "workflow_id": wf.id,
                "type": wf.workflow_type,
                "status": wf.status.name if wf.status else None,
                "started": wf.start_time.isoformat() if wf.start_time else None,
            }
        )
        if len(results) >= min(limit, 50):
            break
    return results


@mcp.tool(annotations=READ_ONLY)
async def get_workflow_status(workflow_id: str) -> dict:
    """What step is this workflow on? Workflow IDs look like offboard-<email> or access-<email>."""
    client = await _client()
    handle = client.get_workflow_handle(workflow_id)
    desc = await handle.describe()
    step = await _step(handle)
    return {
        "workflow_id": workflow_id,
        "type": desc.workflow_type,
        "status": desc.status.name if desc.status else None,
        "current_step": step if step is not None else "unavailable (is the worker running?)",
    }


@mcp.tool(annotations=READ_ONLY)
async def diagnose_workflow(workflow_id: str) -> dict:
    """Why might this workflow be stuck? Checks pending activities, retries and the worker."""
    client = await _client()
    handle = client.get_workflow_handle(workflow_id)
    desc = await handle.describe()
    step = await _step(handle)

    pending: list[PendingActivity] = []
    for p in desc.raw_description.pending_activities:
        failure = p.last_failure.message if p.HasField("last_failure") else None
        pending.append(PendingActivity(p.activity_type.name, p.attempt, failure))

    status = desc.status.name if desc.status else "UNKNOWN"
    return {
        "workflow_id": workflow_id,
        "status": status,
        "current_step": step,
        "pending_activities": [p.__dict__ for p in pending],
        "hints": hints_for(status, pending, query_answered=step is not None),
    }


if __name__ == "__main__":
    mcp.run()  # stdio transport; never print to stdout in this file
