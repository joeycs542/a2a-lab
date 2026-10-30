import asyncio
import os
import signal
import socket
from contextlib import ExitStack
from pathlib import Path

import httpx
import pytest

from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.domain.roles import services_for
from a2a_lab.security.identity import initialize_security, load_client_keys, load_server_keys
from a2a_lab.web.server import create_web_app

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Supervisor uses inherited sockets")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    initialize_security(tmp_path / "keys", topology="discovery")
    ports = {}
    with ExitStack() as stack:
        for role in services_for("discovery"):
            listener = stack.enter_context(socket.socket())
            listener.bind(("127.0.0.1", 0))
            ports[f"{role}_port"] = listener.getsockname()[1]
        return Settings(
            _env_file=None,
            profile="local-secure",
            topology="discovery",
            discovery_mode="review",
            credentials_directory=tmp_path / "keys",
            fixture_delay_seconds=0.4,
            **ports,
        )


async def test_browser_review_trace_isolation_and_cancel(settings: Settings) -> None:
    async with running_agents(settings, lambda _: None):
        app = create_web_app(settings)
        async with (
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url=settings.web_origin
            ) as alice,
            httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url=settings.web_origin
            ) as other,
        ):
            session = (await alice.get("/api/session")).json()
            await other.get("/api/session")
            headers = {"Origin": settings.web_origin, "X-Lab-CSRF": session["csrf"]}
            started = await alice.post(
                "/api/ask", json={"text": "runbook security release"}, headers=headers
            )
            assert started.status_code == 202, started.text
            task_id = started.json()["task_id"]
            assert (await other.get(f"/api/task?id={task_id}")).status_code == 404
            async with asyncio.timeout(10):
                while True:
                    response = await alice.get(f"/api/task?id={task_id}")
                    assert response.status_code == 200, response.text
                    result = response.json()
                    if result["state"] == "TASK_STATE_COMPLETED":
                        break
                    await asyncio.sleep(0.03)
            assert len(result["result"]["references"]) == 3
            assert result["question"] == "runbook security release"
            assert all(
                f"{role}: completed" in result["result"]["answer"]
                for role in ("runbook", "security", "release")
            )
            assert any("directory.search" in event for event in result["events"])
            assert sum("selection.selected" in event for event in result["events"]) == 3
            keys = load_client_keys(settings.credentials_directory)
            url = f"{settings.agent_base_url('coordinator')}/discovery/trace"
            async with httpx.AsyncClient(trust_env=False) as http:
                for owner, expected in [("alice", 200), ("bob", 404)]:
                    trace = await http.post(
                        url,
                        json={"task_id": task_id},
                        headers={"Authorization": keys.select(owner, "coordinator").bearer()},
                    )
                    assert trace.status_code == expected
            slow = await alice.post("/api/ask", json={"text": "[slow] release"}, headers=headers)
            slow_id = slow.json()["task_id"]
            cancel = await alice.post("/api/cancel", json={"task_id": slow_id}, headers=headers)
            assert cancel.status_code == 200
            final = (await alice.get(f"/api/task?id={slow_id}")).json()
            assert final["state"] == "TASK_STATE_CANCELED" and "result" not in final
            assert final["question"] == "[slow] release"
            changed = await alice.post("/api/identity", json={"owner": "bob"}, headers=headers)
            assert changed.status_code == 200
            assert (await alice.get(f"/api/task?id={task_id}")).status_code == 404


async def test_review_failure_is_explicit_and_sends_are_bounded(settings: Settings) -> None:
    from a2a_lab.a2a.client import PeerClient

    events: list[str] = []
    async with running_agents(settings, events.append):
        result = await PeerClient(settings, "coordinator", events.append).call(
            "[fail] runbook release"
        )
        assert "Incomplete review" in result.answer.answer
        assert (
            "runbook: failed" in result.answer.answer and "release: failed" in result.answer.answer
        )
        assert not result.answer.references
        assert sum("rpc.send agent=runbook" in line for line in events) == 1
        assert sum("rpc.send agent=release" in line for line in events) == 1


async def test_partial_review_keeps_successful_findings_and_private_topics(
    settings: Settings,
) -> None:
    from a2a_lab.a2a.client import PeerClient

    events: list[str] = []
    async with running_agents(settings, events.append):
        bob = await PeerClient(settings, "coordinator", events.append, owner="bob").call(
            "runbook security release"
        )
        assert "Incomplete review" in bob.answer.answer
        assert len(bob.answer.references) == 2
        assert "security: completed" not in bob.answer.answer
        assert not any("rpc.send agent=security" in event for event in events)
        pid = next(
            int(line.split("pid=")[1])
            for line in events
            if line.startswith("supervisor.started agent=runbook")
        )
        os.kill(pid, signal.SIGTERM)
        await asyncio.sleep(0.1)
        events.clear()
        partial = await PeerClient(settings, "coordinator", events.append).call("runbook release")
        assert "Incomplete review" in partial.answer.answer
        assert "release: completed" in partial.answer.answer
        assert len(partial.answer.references) == 1
        assert any("selection.excluded agent=runbook" in event for event in events)
        assert not any("rpc.send agent=runbook" in event for event in events)


async def test_review_cancellation_owns_every_started_child(settings: Settings) -> None:
    from a2a_lab.a2a.client import PeerClient

    events: list[str] = []
    settings = settings.model_copy(update={"fixture_delay_seconds": 2})
    async with running_agents(settings, events.append):
        client = PeerClient(settings, "coordinator", events.append)
        root = await client.start("[slow] runbook security release")
        async with asyncio.timeout(5):
            while (
                sum(
                    "[coordinator pid=" in line and "delegation.started agent=" in line
                    for line in events
                )
                < 3
            ):
                await asyncio.sleep(0.01)
        await client.cancel_task(root.id)
        async with asyncio.timeout(5):
            while sum("delegation.cancelled agent=" in line for line in events) < 3:
                await asyncio.sleep(0.01)
        keys = load_server_keys(settings.credentials_directory, "coordinator")
        for role in ("runbook", "security", "release"):
            line = next(line for line in events if f"delegation.started agent={role}" in line)
            child_id = line.split("task='")[1].split("'")[0]
            child = await PeerClient(
                settings, role, events.append, credential=keys.delegated("alice", role)
            ).get_task(child_id)
            assert child.status.state == 5 and not child.artifacts
        await asyncio.sleep(0.1)
        final = await client.get_task(root.id)
        assert final.status.state == 5 and not final.artifacts


async def test_review_timeout_reports_unknown_without_blind_retry(settings: Settings) -> None:
    from a2a_lab.a2a.client import PeerClient

    events: list[str] = []
    settings = settings.model_copy(update={"fixture_delay_seconds": 4})
    async with running_agents(settings, events.append):
        result = await PeerClient(settings, "coordinator", events.append).call("[slow] release")
        assert "Incomplete review" in result.answer.answer
        assert "release: unknown" in result.answer.answer
        assert not result.answer.references
        assert sum("rpc.send agent=release" in line for line in events) == 1
        assert any("delegation.cancelled agent=release" in line for line in events)
