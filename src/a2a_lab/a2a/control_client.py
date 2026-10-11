"""Operator-only calls to the secure coordinator's synthetic control API."""

import asyncio
from typing import Literal

import httpx

from a2a_lab.a2a.limits import BoundedTransport
from a2a_lab.config import Settings
from a2a_lab.security.identity import Owner, SecurityError, load_client_keys


async def control_request(
    settings: Settings,
    owner: Owner,
    operation: Literal["propose", "approve", "execute"],
    data: dict[str, object],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    """Select the human credential only for an explicit operator approval."""
    if settings.profile != "local-secure":
        raise SecurityError("Action controls require the local-secure profile.")
    path = {
        "propose": "/actions/proposals",
        "approve": "/control/approve",
        "execute": "/actions/execute",
    }[operation]
    url = f"{settings.agent_base_url('coordinator')}{path}"
    credential = load_client_keys(settings.credentials_directory).select(
        owner, "coordinator", approval=operation == "approve"
    )
    async with (
        asyncio.timeout(settings.request_timeout_seconds),
        httpx.AsyncClient(
            transport=BoundedTransport(frozenset({url}), settings.max_payload_bytes, transport),
            timeout=settings.request_timeout_seconds,
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": credential.bearer(), "Accept-Encoding": "identity"},
        ) as client,
    ):
        response = await client.post(url, json=data)
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError as error:
            raise SecurityError("Control response is malformed.") from error
        if not isinstance(result, dict):
            raise SecurityError("Control response is malformed.")
        return result
