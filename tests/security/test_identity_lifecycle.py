import asyncio
import json
import time

import httpx
import pytest
from starlette.requests import Request

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.identity import AuthenticatedContextBuilder
from a2a_lab.a2a.server import create_agent_app
from a2a_lab.agents.knowledge import KnowledgeAgent
from a2a_lab.config import Settings
from a2a_lab.domain.models import Answer
from a2a_lab.security.identity import current_principal, load_client_keys, load_server_keys


def rpc(method: str, params: dict[str, object]) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": "security-check", "method": method, "params": params}


def question(text: str = "runbook") -> dict[str, object]:
    return {"message": {"messageId": "question", "role": "ROLE_USER", "parts": [{"text": text}]}}


@pytest.mark.parametrize(
    "failure", ["missing", "invalid", "expired", "wrong-audience", "duplicate"]
)
async def test_authentication_rejects_credentials_before_execution(
    secure_settings: Settings, failure: str
) -> None:
    keys = load_server_keys(secure_settings.credentials_directory, "knowledge")
    clients = load_client_keys(secure_settings.credentials_directory)
    events: list[str] = []
    if failure == "expired":
        keys = keys.model_copy(
            update={
                "verifiers": tuple(
                    record.model_copy(update={"expires_at": time.time() - 1})
                    for record in keys.verifiers
                )
            }
        )
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(), events.append, keys=keys)
    headers = [("A2A-Version", "1.0")]
    if failure == "invalid":
        headers.append(("Authorization", "Bearer invalid"))
    elif failure not in {"missing"}:
        target = "coordinator" if failure == "wrong-audience" else "knowledge"
        headers.append(("Authorization", clients.select("alice", target).bearer()))
        if failure == "duplicate":
            headers.append(headers[-1])
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            secure_settings.agent_base_url("knowledge") + "/a2a/jsonrpc",
            headers=headers,
            json=rpc("SendMessage", question("private-question-do-not-log")),
        )
    assert response.status_code == 401
    assert not any("workflow.started" in event for event in events)
    assert "private-question-do-not-log" not in "\n".join(events)


async def test_reads_artifacts_lists_and_cancellation_are_owner_scoped(
    secure_settings: Settings,
) -> None:
    events: list[str] = []
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(0.2), events.append)
    alice = PeerClient(
        secure_settings, "knowledge", events.append, transport=httpx.ASGITransport(app=app)
    )
    bob = PeerClient(
        secure_settings,
        "knowledge",
        events.append,
        owner="bob",
        transport=httpx.ASGITransport(app=app),
    )
    async with app.router.lifespan_context(app):
        task = await alice.start("[slow] runbook")
        with pytest.raises(LookupFailure):
            await bob.get_task(task.id)
        with pytest.raises(LookupFailure):
            await bob.cancel_task(task.id)
        assert len((await bob.list_tasks()).tasks) == 0
        assert (await alice.list_tasks()).tasks[0].id == task.id
        cancelled = await alice.cancel_task(task.id)
        assert cancelled.status.state == 5
        await asyncio.sleep(0.25)
        final = await alice.get_task(task.id)
        assert final.status.state == 5
        assert len(final.artifacts) == 0
    secrets = load_client_keys(secure_settings.credentials_directory).credentials
    trace = "\n".join(events)
    assert all(credential.token.get_secret_value() not in trace for credential in secrets)


async def test_completed_artifact_is_visible_only_to_owner(secure_settings: Settings) -> None:
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(), lambda event: None)
    alice = PeerClient(
        secure_settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    bob = PeerClient(
        secure_settings,
        "knowledge",
        lambda event: None,
        owner="bob",
        transport=httpx.ASGITransport(app=app),
    )
    async with app.router.lifespan_context(app):
        result = await alice.call("runbook")
        stored = await alice.get_task(result.task_id)
        assert stored.artifacts[0].name == "engineering-answer"
        with pytest.raises(LookupFailure):
            await bob.get_task(result.task_id)
        with pytest.raises(LookupFailure):
            await alice.cancel_task(result.task_id)


async def test_cancellation_blocks_late_results_even_if_provider_suppresses_cancel(
    secure_settings: Settings,
) -> None:
    started = asyncio.Event()

    class Resistant:
        async def answer(self, text: str) -> Answer:
            started.set()
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                await asyncio.sleep(0.01)
                return Answer(answer="late-result-must-not-be-published", references=())
            return Answer(answer="ordinary result", references=())

    app = create_agent_app("knowledge", secure_settings, Resistant(), lambda event: None)
    client = PeerClient(
        secure_settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    async with app.router.lifespan_context(app):
        task = await client.start("runbook")
        await asyncio.wait_for(started.wait(), 1)
        assert (await client.cancel_task(task.id)).status.state == 5
        final = await client.get_task(task.id)
        assert final.status.state == 5
        assert not final.artifacts


async def test_shutdown_cancels_owned_child_work(secure_settings: Settings) -> None:
    started = asyncio.Event()
    stopped = asyncio.Event()

    class Slow:
        async def answer(self, text: str) -> Answer:
            started.set()
            try:
                await asyncio.sleep(10)
            finally:
                stopped.set()
            return Answer(answer="late", references=())

    app = create_agent_app("knowledge", secure_settings, Slow(), lambda event: None)
    client = PeerClient(
        secure_settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    async with app.router.lifespan_context(app):
        await client.start("runbook")
        await asyncio.wait_for(started.wait(), 1)
    assert stopped.is_set()


async def test_untrusted_owner_metadata_cannot_change_identity(secure_settings: Settings) -> None:
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(), lambda event: None)
    credential = load_client_keys(secure_settings.credentials_directory).select(
        "alice", "knowledge"
    )
    body = question()
    body["metadata"] = {"owner": "bob", "approved": True, "role": "approver"}
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client,
    ):
        response = await client.post(
            secure_settings.agent_base_url("knowledge") + "/a2a/jsonrpc",
            headers={"A2A-Version": "1.0", "Authorization": credential.bearer(), "X-Owner": "bob"},
            json=rpc("SendMessage", body),
        )
        task_id = response.json()["result"]["task"]["id"]
        bob = PeerClient(
            secure_settings,
            "knowledge",
            lambda event: None,
            owner="bob",
            transport=httpx.ASGITransport(app=app),
        )
        with pytest.raises(LookupFailure):
            await bob.get_task(task_id)


def test_sdk_context_preserves_version_without_bearer_secrets(secure_settings: Settings) -> None:
    credential = load_client_keys(secure_settings.credentials_directory).select(
        "alice", "knowledge"
    )
    context = AuthenticatedContextBuilder().build(
        Request(
            {
                "type": "http",
                "headers": [
                    (b"a2a-version", b"1.0"),
                    (b"authorization", credential.bearer().encode()),
                ],
                "lab_principal": credential.principal,
                "lab_correlation": "trusted-correlation",
            }
        )
    )
    assert context.state["headers"] == {"a2a-version": "1.0"}
    assert context.user.user_name == "alice:alice"
    assert credential.token.get_secret_value() not in repr(context.state)


async def test_controlled_failure_and_timeout_produce_failed_tasks(
    secure_settings: Settings,
) -> None:
    settings = Settings(**{**secure_settings.model_dump(), "request_timeout_seconds": 0.05})
    app = create_agent_app("knowledge", settings, KnowledgeAgent(0.2), lambda event: None)
    client = PeerClient(
        settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    async with app.router.lifespan_context(app):
        failure = await client.start("[fail] runbook")
        slow = await client.start("[slow] runbook")
        await asyncio.sleep(0.08)
        assert (await client.get_task(failure.id)).status.state == 4
        assert (await client.get_task(slow.id)).status.state == 4


async def test_retention_budget_rejects_new_work_without_losing_owned_task(
    secure_settings: Settings,
) -> None:
    settings = Settings(**{**secure_settings.model_dump(), "max_retained_tasks": 1})
    app = create_agent_app("knowledge", settings, KnowledgeAgent(), lambda event: None)
    client = PeerClient(
        settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    async with app.router.lifespan_context(app):
        first = await client.call("runbook")
        with pytest.raises(LookupFailure):
            await client.call("security")
        assert (await client.get_task(first.task_id)).status.state == 3
        assert len((await client.list_tasks()).tasks) == 1


async def test_last_allowed_poll_can_return_a_completed_result(secure_settings: Settings) -> None:
    settings = Settings(**{**secure_settings.model_dump(), "max_task_polls": 1})
    app = create_agent_app("knowledge", settings, KnowledgeAgent(), lambda event: None)
    client = PeerClient(
        settings, "knowledge", lambda event: None, transport=httpx.ASGITransport(app=app)
    )
    async with app.router.lifespan_context(app):
        result = await client.call("runbook")
        assert result.answer.references[0].fixture_id == "runbook"


async def test_polling_budget_cancels_pending_work_and_does_not_retry_send(
    secure_settings: Settings,
) -> None:
    settings = Settings(**{**secure_settings.model_dump(), "max_task_polls": 1})
    app = create_agent_app("knowledge", settings, KnowledgeAgent(2), lambda event: None)
    inner = httpx.ASGITransport(app=app)
    methods: list[str] = []

    async def record(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            methods.append(json.loads(request.content)["method"])
        return await inner.handle_async_request(request)

    client = PeerClient(
        settings, "knowledge", lambda event: None, transport=httpx.MockTransport(record)
    )
    async with app.router.lifespan_context(app):
        with pytest.raises(LookupFailure, match="polling budget"):
            await client.call("[slow] runbook")
        assert methods.count("SendMessage") == 1
        assert methods.count("GetTask") == 1
        assert methods.count("CancelTask") == 1
        listing = await client.list_tasks()
        assert listing.tasks[0].status.state == 5


async def test_delegation_uses_service_authority_instead_of_forwarding_user_token(
    secure_settings: Settings,
) -> None:
    server = load_server_keys(secure_settings.credentials_directory, "coordinator")
    users = load_client_keys(secure_settings.credentials_directory)
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(), lambda event: None)
    inner = httpx.ASGITransport(app=app)
    requests: list[httpx.Request] = []

    async def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return await inner.handle_async_request(request)

    marker = current_principal.set(users.select("alice", "coordinator").principal)
    try:
        async with app.router.lifespan_context(app):
            result = await PeerClient(
                secure_settings,
                "knowledge",
                lambda event: None,
                server_keys=server,
                transport=httpx.MockTransport(record),
            ).call("runbook")
            assert all(
                request.headers["Authorization"] == server.delegated("alice").bearer()
                for request in requests
            )
            assert all(
                request.headers["Authorization"] != users.select("alice", "coordinator").bearer()
                for request in requests
            )
            with pytest.raises(LookupFailure):
                await PeerClient(
                    secure_settings,
                    "knowledge",
                    lambda event: None,
                    transport=httpx.ASGITransport(app=app),
                ).get_task(result.task_id)
    finally:
        current_principal.reset(marker)
