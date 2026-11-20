"""Small async Okta client for the offboarding activities.

Config comes from environment variables (see .env.example):
  OKTA_ORG_URL    e.g. https://dev-12345678.okta.com
  OKTA_API_TOKEN  an SSWS API token (keep it out of git)
"""
import os
from urllib.parse import quote

import httpx
from temporalio.exceptions import ApplicationError


def build_client() -> httpx.AsyncClient:
    org = os.environ["OKTA_ORG_URL"].rstrip("/")
    token = os.environ["OKTA_API_TOKEN"]
    return httpx.AsyncClient(
        base_url=org,
        headers={"Authorization": f"SSWS {token}", "Accept": "application/json"},
        timeout=15,
    )


def _fail(resp: httpx.Response, what: str) -> None:
    """Turn an HTTP error into the right Temporal failure.

    401/403/404 will not fix themselves, so they are non-retryable.
    429 and 5xx raise a normal error, so Temporal retries with backoff.
    """
    if resp.status_code in (401, 403, 404):
        raise ApplicationError(
            f"Okta {what} failed: HTTP {resp.status_code}", non_retryable=True
        )
    raise RuntimeError(f"Okta {what} failed: HTTP {resp.status_code}")


async def suspend_user(client: httpx.AsyncClient, login: str) -> str:
    """Suspend the user and clear their sessions. Safe to call more than once.

    Returns "suspended" or "already-suspended".
    """
    resp = await client.get(f"/api/v1/users/{quote(login, safe='@')}")
    if resp.status_code != 200:
        _fail(resp, f"lookup of {login}")
    user = resp.json()
    user_id, status = user["id"], user["status"]

    outcome = "already-suspended"
    if status == "ACTIVE":
        resp = await client.post(f"/api/v1/users/{user_id}/lifecycle/suspend")
        if resp.status_code != 200:
            _fail(resp, f"suspend of {login}")
        outcome = "suspended"
    elif status != "SUSPENDED":
        # e.g. DEPROVISIONED or STAGED: suspending makes no sense, don't retry.
        raise ApplicationError(
            f"Cannot suspend {login}: user status is {status}", non_retryable=True
        )

    # Always clear sessions, even if the user was already suspended.
    resp = await client.delete(f"/api/v1/users/{user_id}/sessions")
    if resp.status_code not in (200, 204):
        _fail(resp, f"session clear for {login}")
    return outcome
