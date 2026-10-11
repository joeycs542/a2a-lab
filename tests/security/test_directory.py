import json
from pathlib import Path

import httpx
import pytest
from google.protobuf.json_format import MessageToDict

from a2a_lab.a2a.cards import build_agent_card
from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.directory import DirectoryClient, expected_candidate
from a2a_lab.bootstrap import build_app
from a2a_lab.config import Settings
from a2a_lab.domain.discovery import SearchRequest
from a2a_lab.security.identity import initialize_security, load_client_keys, load_server_keys


@pytest.fixture
def discovery_settings(tmp_path: Path) -> Settings:
    directory = tmp_path / "keys"
    initialize_security(directory, topology="discovery")
    return Settings(
        _env_file=None,
        profile="local-secure",
        topology="discovery",
        credentials_directory=directory,
    )


async def test_directory_auth_scope_and_no_registration(discovery_settings: Settings) -> None:
    settings = discovery_settings
    keys = load_client_keys(settings.credentials_directory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=build_app("directory", settings)),
        base_url=settings.agent_base_url("directory"),
    ) as client:
        query = {"topics": ["runbook", "security", "release"]}
        assert (await client.post("/search", json=query)).status_code == 401
        wrong = keys.select("alice", "coordinator").bearer()
        assert (
            await client.post("/search", json=query, headers={"Authorization": wrong})
        ).status_code == 401
        for owner, expected in [
            ("alice", ["runbook", "security", "release"]),
            ("bob", ["runbook", "release"]),
        ]:
            headers = {"Authorization": keys.select(owner, "directory").bearer()}
            response = await client.post("/search", json=query, headers=headers)
            assert response.status_code == 200
            assert [c["peer_id"] for c in response.json()["candidates"]] == expected
            assert (await client.post("/register", json=query, headers=headers)).status_code == 403
            assert (
                await client.post("/search", json={**query, "owner": "alice"}, headers=headers)
            ).status_code == 422
        assert (await client.get("/health")).json() == {"status": "ok"}


async def test_security_peer_enforces_owner_even_with_valid_token(
    discovery_settings: Settings,
) -> None:
    settings = discovery_settings
    keys = load_client_keys(settings.credentials_directory)
    app = build_app("security", settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=settings.agent_base_url("security")
    ) as client:
        bob = keys.select("bob", "security").bearer()
        result = await client.post("/a2a/jsonrpc", json={}, headers={"Authorization": bob})
        assert result.status_code == 403
    service_keys = load_server_keys(settings.credentials_directory, "coordinator")
    credential = service_keys.delegated("bob", "security")
    with pytest.raises(LookupFailure):
        await PeerClient(
            settings,
            "security",
            lambda _: None,
            credential=credential,
            transport=httpx.ASGITransport(app=app),
        ).discover()
        # Cards are public; discovery is not authorization. The RPC below must be denied.
        await PeerClient(
            settings,
            "security",
            lambda _: None,
            credential=credential,
            transport=httpx.ASGITransport(app=app),
        ).call("security")


@pytest.mark.parametrize("alteration", ["url", "skill", "duplicate", "outside-query", "forbidden"])
async def test_substituted_catalog_data_cannot_expand_authority(
    discovery_settings: Settings,
    alteration: str,
) -> None:
    settings = discovery_settings
    candidate = expected_candidate("runbook", settings).model_dump(mode="json")
    candidates = [candidate]
    owner = "alice"
    if alteration == "url":
        candidate["rpc_url"] = "http://127.0.0.1:9999/a2a/jsonrpc"
    elif alteration == "skill":
        candidate["skill_id"] = "unapproved-skill"
    elif alteration == "duplicate":
        candidates.append(candidate)
    elif alteration == "outside-query":
        candidates = [expected_candidate("release", settings).model_dump(mode="json")]
    elif alteration == "forbidden":
        candidates = [expected_candidate("security", settings).model_dump(mode="json")]
        owner = "bob"
    calls: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"candidates": candidates})

    topics = ("runbook", "security") if alteration == "forbidden" else ("runbook",)
    with pytest.raises(LookupFailure):
        await DirectoryClient(
            settings, lambda _: None, owner=owner, transport=httpx.MockTransport(respond)
        ).search(SearchRequest(topics=topics))
    assert len(calls) == 1
    assert str(calls[0].url) == f"{settings.agent_base_url('directory')}/search"
    assert "owner" not in json.loads(calls[0].content)


async def test_direct_search_uses_only_the_directory_recipient_token(
    discovery_settings: Settings,
) -> None:
    settings = discovery_settings
    keys = load_client_keys(settings.credentials_directory)

    async def respond(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == keys.select("alice", "directory").bearer()
        assert request.headers["Authorization"] != keys.select("alice", "coordinator").bearer()
        return httpx.Response(200, json={"candidates": []})

    result = await DirectoryClient(
        settings, lambda _: None, transport=httpx.MockTransport(respond)
    ).search(SearchRequest(topics=("runbook",)))
    assert not result.candidates


@pytest.mark.parametrize("alteration", ["skill", "endpoint", "version"])
async def test_incompatible_specialist_card_stops_before_rpc(
    discovery_settings: Settings,
    alteration: str,
) -> None:
    settings = discovery_settings
    card = build_agent_card("runbook", settings)
    if alteration == "skill":
        card.skills[0].id = "security-impersonation"
    elif alteration == "endpoint":
        card.supported_interfaces[0].url = settings.agent_base_url("security") + "/a2a/jsonrpc"
    else:
        card.supported_interfaces[0].protocol_version = "0.3"
    requests: list[httpx.Request] = []

    async def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=MessageToDict(card))

    with pytest.raises(LookupFailure):
        await PeerClient(
            settings, "runbook", lambda _: None, transport=httpx.MockTransport(respond)
        ).call("runbook")
    assert len(requests) == 1 and requests[0].method == "GET"
