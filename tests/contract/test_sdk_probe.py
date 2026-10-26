import httpx
import pytest
from a2a.server.request_handlers.response_helpers import agent_card_to_dict

from a2a_lab.a2a.probe import PROBE_REPLY, build_probe_card, create_probe_app, verify_sdk
from a2a_lab.config import Settings


class RecordingTransport(httpx.AsyncBaseTransport):
    def __init__(self, app: object) -> None:
        self.inner = httpx.ASGITransport(app=app)
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return await self.inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self.inner.aclose()


async def test_official_client_discovers_and_sends_a_v1_request() -> None:
    settings = Settings(_env_file=None)
    app = create_probe_app(settings)
    transport = RecordingTransport(app)
    async with app.router.lifespan_context(app):
        report = await verify_sdk(settings, transport=transport)
    assert report["result"] == "ok"
    assert report["response"] == PROBE_REPLY
    assert transport.requests[0].url.path == "/.well-known/agent-card.json"
    rpc = [request for request in transport.requests if request.method == "POST"]
    assert len(rpc) == 1
    assert rpc[0].url.path == "/a2a/jsonrpc"
    assert rpc[0].headers["A2A-Version"] == "1.0"


@pytest.mark.parametrize(
    "parts",
    [
        [],
        [{"text": "   "}],
        [{"text": "x" * 1001}],
        [{"data": {"instruction": "perform another operation"}}],
    ],
)
async def test_probe_rejects_unsupported_or_excessive_input(parts: list[dict[str, object]]) -> None:
    settings = Settings(_env_file=None)
    app = create_probe_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            settings.rpc_url,
            headers={"A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "invalid-input",
                "method": "SendMessage",
                "params": {"message": {"messageId": "input", "role": "ROLE_USER", "parts": parts}},
            },
        )
    body = response.json()
    assert "error" in body
    assert "result" not in body


async def test_served_card_declares_only_the_configured_probe() -> None:
    settings = Settings(_env_file=None, port=8200)
    app = create_probe_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get(f"{settings.base_url}/.well-known/agent-card.json")
    assert response.status_code == 200
    card = response.json()
    assert card["supportedInterfaces"] == [
        {"url": settings.rpc_url, "protocolBinding": "JSONRPC", "protocolVersion": "1.0"}
    ]
    assert card["defaultInputModes"] == ["text/plain"]
    assert not card["capabilities"].get("streaming", False)
    assert not card["capabilities"].get("pushNotifications", False)
    assert card["skills"][0]["id"] == "sdk-probe"


@pytest.mark.parametrize("protocol_version", ["0.3", "1.1", "", "malformed"])
async def test_probe_does_not_silently_accept_another_protocol(protocol_version: str) -> None:
    settings = Settings(_env_file=None)
    app = create_probe_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            settings.rpc_url,
            headers={"A2A-Version": protocol_version},
            json={
                "jsonrpc": "2.0",
                "id": "unsupported-version",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "version-check",
                        "role": "ROLE_USER",
                        "parts": [{"text": "p"}],
                    }
                },
            },
        )
    assert "error" in response.json()
    assert "result" not in response.json()


async def test_patch_number_does_not_change_protocol_compatibility() -> None:
    settings = Settings(_env_file=None)
    app = create_probe_app(settings)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            settings.rpc_url,
            headers={"A2A-Version": "1.0.7"},
            json={
                "jsonrpc": "2.0",
                "id": "patch-number",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "patch-check",
                        "role": "ROLE_USER",
                        "parts": [{"text": "p"}],
                    }
                },
            },
        )
    assert response.json()["result"]["message"]["parts"][0]["text"] == PROBE_REPLY


@pytest.mark.parametrize(
    "changed",
    [
        {"url": "http://169.254.169.254/latest/meta-data"},
        {"protocolVersion": "0.3"},
        {"protocolBinding": "HTTP+JSON"},
    ],
)
async def test_changed_card_cannot_redirect_the_probe_check(changed: dict[str, str]) -> None:
    settings = Settings(_env_file=None)
    card = agent_card_to_dict(build_probe_card(settings))
    card["supportedInterfaces"][0].update(changed)
    requests: list[httpx.Request] = []

    def reply(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=card)

    with pytest.raises(ValueError, match="does not match"):
        await verify_sdk(settings, transport=httpx.MockTransport(reply))
    assert len(requests) == 1
    assert requests[0].url.path == "/.well-known/agent-card.json"
