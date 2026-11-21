"""Plain-Python helper that turns what Temporal reports into plain-English hints.

Kept free of Temporal and MCP imports so it is easy to unit test.
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class PendingActivity:
    name: str
    attempt: int
    last_failure: Optional[str] = None


def hints_for(status: str, pending: List[PendingActivity], query_answered: bool) -> List[str]:
    """status is the Temporal status name, e.g. RUNNING, COMPLETED, FAILED."""
    if status != "RUNNING":
        if status == "FAILED":
            return ["Workflow FAILED. Read the failure in the event history; start a new run once the cause is fixed."]
        return [f"Workflow is {status}; nothing is running."]

    hints: List[str] = []
    for p in pending:
        if p.attempt > 1:
            hints.append(
                f"Activity {p.name} is on attempt {p.attempt}; last failure: "
                f"{p.last_failure or 'unknown'}. Retries back off and stop after 5 attempts."
            )
        else:
            hints.append(f"Activity {p.name} is running (attempt 1).")

    if not query_answered:
        hints.append(
            "The status query got no answer, so the worker is probably not running. "
            "Start it and the workflow will resume."
        )
    elif not pending:
        hints.append(
            "No activity is running: the workflow is waiting on a timer or on an approval signal."
        )
    return hints
