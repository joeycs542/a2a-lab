from pathlib import Path

import httpx
import pytest

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.bootstrap import build_app
from a2a_lab.config import Settings
from a2a_lab.security.identity import initialize_security, load_client_keys


@pytest.mark.parametrize("profile", ["local-demo", "local-secure"])
@pytest.mark.parametrize("workflow", ["notes", "release-readiness"])
async def test_selected_workflow_serves_truthful_card_and_executes_through_sdk(
    profile: str, workflow: str, tmp_path: Path
) -> None:
    directory = tmp_path / "security"
    initialize_security(directory)
    settings = Settings(
        _env_file=None,
        profile=profile,
        knowledge_workflow=workflow,
        knowledge_port=8202,
        coordinator_port=8201,
        credentials_directory=directory,
    )
    app = build_app("knowledge", settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport) as http_client,
    ):
        response = await http_client.get(
            f"{settings.agent_base_url('knowledge')}/.well-known/agent-card.json"
        )
        card = response.json()
        assert card["supportedInterfaces"][0]["url"] == "http://127.0.0.1:8202/a2a/jsonrpc"
        for credential in load_client_keys(directory).credentials:
            assert credential.token.get_secret_value() not in response.text
        assert bool(card.get("securityRequirements")) == (profile == "local-secure")
        question = "What should we review before a release?" if workflow != "notes" else "runbook"
        result = await PeerClient(settings, "knowledge", lambda _: None, transport=transport).call(
            question
        )
        assert result.answer.references[0].fixture_id == (
            "release-readiness" if workflow != "notes" else "runbook"
        )
        example_result = await PeerClient(
            settings, "knowledge", lambda _: None, transport=transport
        ).call(card["skills"][0]["examples"][0])
        assert example_result.answer.references


async def test_workflow_capability_mismatch_stops_before_rpc() -> None:
    serving = Settings(_env_file=None, knowledge_workflow="release-readiness")
    app = build_app("knowledge", serving)
    inner = httpx.ASGITransport(app=app)
    calls: list[str] = []

    async def record(request: httpx.Request) -> httpx.Response:
        calls.append(request.method)
        return await inner.handle_async_request(request)

    async with app.router.lifespan_context(app):
        with pytest.raises(LookupFailure):
            await PeerClient(
                Settings(_env_file=None),
                "knowledge",
                lambda _: None,
                transport=httpx.MockTransport(record),
            ).call("release readiness")
    assert calls == ["GET"]


@pytest.mark.parametrize(
    "method", ["SendStreamingMessage", "GetExtendedAgentCard", "NotALabMethod"]
)
async def test_unadvertised_operations_return_protocol_errors(method: str) -> None:
    settings = Settings(_env_file=None, knowledge_workflow="release-readiness")
    app = build_app("knowledge", settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            settings.agent_base_url("knowledge") + "/a2a/jsonrpc",
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "unsupported",
                "method": method,
                "params": {
                    "message": {
                        "messageId": "unsupported",
                        "role": "ROLE_USER",
                        "parts": [{"text": "release readiness"}],
                    }
                }
                if method == "SendStreamingMessage"
                else {},
            },
        )
    assert "error" in response.json()
    assert "result" not in response.json()


async def test_readiness_rejects_non_text_content() -> None:
    settings = Settings(_env_file=None, knowledge_workflow="release-readiness")
    app = build_app("knowledge", settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            settings.agent_base_url("knowledge") + "/a2a/jsonrpc",
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "non-text",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "non-text",
                        "role": "ROLE_USER",
                        "parts": [{"mediaType": "application/json", "data": {"approved": True}}],
                    }
                },
            },
        )
    assert "error" in response.json()
    assert "result" not in response.json()
