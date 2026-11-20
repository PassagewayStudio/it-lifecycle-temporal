"""Okta client tests against a mocked HTTP transport. Nothing touches a real tenant."""
import httpx
import pytest
from temporalio.exceptions import ApplicationError

import okta_client


def make_client(user_status, calls, lookup_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            if lookup_status != 200:
                return httpx.Response(lookup_status, json={})
            return httpx.Response(200, json={"id": "00u123", "status": user_status})
        if request.url.path.endswith("/lifecycle/suspend"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/sessions"):
            return httpx.Response(204)
        return httpx.Response(500)

    return httpx.AsyncClient(
        base_url="https://example.okta.com", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_active_user_is_suspended_and_sessions_cleared():
    calls = []
    async with make_client("ACTIVE", calls) as client:
        assert await okta_client.suspend_user(client, "jane.doe@example.com") == "suspended"
    assert ("POST", "/api/v1/users/00u123/lifecycle/suspend") in calls
    assert ("DELETE", "/api/v1/users/00u123/sessions") in calls


@pytest.mark.asyncio
async def test_already_suspended_user_is_not_suspended_again():
    calls = []
    async with make_client("SUSPENDED", calls) as client:
        assert (
            await okta_client.suspend_user(client, "jane.doe@example.com")
            == "already-suspended"
        )
    assert not any(path.endswith("/lifecycle/suspend") for _, path in calls)
    assert ("DELETE", "/api/v1/users/00u123/sessions") in calls


@pytest.mark.asyncio
async def test_missing_user_fails_without_retry():
    async with make_client("ACTIVE", [], lookup_status=404) as client:
        with pytest.raises(ApplicationError) as exc:
            await okta_client.suspend_user(client, "nobody@example.com")
    assert exc.value.non_retryable


@pytest.mark.asyncio
async def test_deprovisioned_user_fails_without_retry():
    async with make_client("DEPROVISIONED", []) as client:
        with pytest.raises(ApplicationError) as exc:
            await okta_client.suspend_user(client, "jane.doe@example.com")
    assert exc.value.non_retryable


def group_client(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            return httpx.Response(200, json={"id": "00u123", "status": "ACTIVE"})
        return httpx.Response(204)

    return httpx.AsyncClient(
        base_url="https://example.okta.com", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_add_and_remove_group_membership():
    calls = []
    async with group_client(calls) as client:
        assert await okta_client.add_to_group(client, "jane@example.com", "00g1") == "added"
        assert await okta_client.remove_from_group(client, "jane@example.com", "00g1") == "removed"
    assert ("PUT", "/api/v1/groups/00g1/users/00u123") in calls
    assert ("DELETE", "/api/v1/groups/00g1/users/00u123") in calls


def delete_client(user_status, calls, lookup_status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "GET":
            if lookup_status != 200:
                return httpx.Response(lookup_status, json={})
            return httpx.Response(200, json={"id": "00u123", "status": user_status})
        if request.method == "POST":  # deactivate
            return httpx.Response(200, json={})
        return httpx.Response(204)  # DELETE

    return httpx.AsyncClient(
        base_url="https://example.okta.com", transport=httpx.MockTransport(handler)
    )


@pytest.mark.asyncio
async def test_suspended_user_is_deactivated_then_deleted():
    calls = []
    async with delete_client("SUSPENDED", calls) as client:
        assert await okta_client.delete_user(client, "jane@example.com") == "deleted"
    assert ("POST", "/api/v1/users/00u123/lifecycle/deactivate") in calls
    assert calls[-1] == ("DELETE", "/api/v1/users/00u123")


@pytest.mark.asyncio
async def test_deprovisioned_user_is_deleted_without_deactivating():
    calls = []
    async with delete_client("DEPROVISIONED", calls) as client:
        assert await okta_client.delete_user(client, "jane@example.com") == "deleted"
    assert not any(method == "POST" for method, _ in calls)


@pytest.mark.asyncio
async def test_delete_of_missing_user_is_a_no_op():
    calls = []
    async with delete_client("ACTIVE", calls, lookup_status=404) as client:
        assert await okta_client.delete_user(client, "gone@example.com") == "already-deleted"
    assert calls == [("GET", "/api/v1/users/gone@example.com")]
