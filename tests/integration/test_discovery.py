import asyncio
import os
import signal
import socket
from contextlib import ExitStack
from pathlib import Path

import pytest

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.directory import DirectoryClient
from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.domain.discovery import SearchRequest
from a2a_lab.domain.roles import services_for
from a2a_lab.security.identity import initialize_security, load_server_keys

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Supervisor uses inherited sockets")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    directory = tmp_path / "keys"
    initialize_security(directory, topology="discovery")
    ports = {}
    with ExitStack() as stack:
        for service in services_for("discovery"):
            listener = stack.enter_context(socket.socket())
            listener.bind(("127.0.0.1", 0))
            ports[f"{service}_port"] = listener.getsockname()[1]
        return Settings(
            _env_file=None,
            profile="local-secure",
            topology="discovery",
            credentials_directory=directory,
            fixture_delay_seconds=0.4,
            **ports,
        )


async def test_real_directory_routing_and_explicit_no_match_or_ambiguity(
    settings: Settings,
) -> None:
    events: list[str] = []
    client = PeerClient(settings, "coordinator", events.append)
    async with running_agents(settings, events.append):
        for question, peer, fixture in [
            ("runbook operations", "runbook", "runbook"),
            ("secure security", "security", "secure-delegation"),
            ("release readiness", "release", "release-readiness"),
        ]:
            result = await client.call(question)
            assert f"Selected specialist: {peer}" in result.answer.answer
            assert result.answer.references[0].fixture_id == fixture
            assert any(f"rpc.send agent={peer}" in line for line in events)
        events.clear()
        empty = await client.call("unrelated question")
        assert "No supported topic" in empty.answer.answer
        assert not any("directory.search" in line for line in events)
        tied = await client.call("security release")
        assert "match equally" in tied.answer.answer and not tied.answer.references
        assert not any(
            "rpc.send agent=security" in line or "rpc.send agent=release" in line for line in events
        )
        bob = PeerClient(settings, "coordinator", events.append, owner="bob")
        restricted = await bob.call("security")
        assert "No authorized" in restricted.answer.answer
        direct_bob = PeerClient(settings, "security", events.append, owner="bob")
        with pytest.raises(LookupFailure):
            await direct_bob.call("security")
        catalog = await DirectoryClient(settings, events.append, owner="bob").search(
            SearchRequest(topics=("runbook", "security", "release"))
        )
        assert {entry.peer_id for entry in catalog.candidates} == {"runbook", "release"}


async def test_unavailable_specialist_is_excluded_before_send(settings: Settings) -> None:
    events: list[str] = []
    async with running_agents(settings, events.append):
        pid = next(
            int(line.split("pid=")[1])
            for line in events
            if line.startswith("supervisor.started agent=runbook")
        )
        os.kill(pid, signal.SIGTERM)
        await asyncio.sleep(0.1)
        result = await PeerClient(settings, "coordinator", events.append).call("runbook")
        assert "No authorized" in result.answer.answer and not result.answer.references
        assert any("selection.excluded agent=runbook" in line for line in events)
        assert not any("rpc.send agent=runbook" in line for line in events)


async def test_discovery_cancellation_owns_the_selected_child(settings: Settings) -> None:
    events: list[str] = []
    async with running_agents(settings, events.append):
        client = PeerClient(settings, "coordinator", events.append)
        task = await client.start("[slow] release")
        async with asyncio.timeout(5):
            while not any(
                "[coordinator pid=" in line and "delegation.started agent=release" in line
                for line in events
            ):
                await asyncio.sleep(0.01)
        canceled = await client.cancel_task(task.id)
        assert canceled.status.state == 5
        async with asyncio.timeout(5):
            while not any("delegation.cancelled agent=release" in line for line in events):
                await asyncio.sleep(0.01)
        await asyncio.sleep(0.5)
        stored = await client.get_task(task.id)
        assert stored.status.state == 5 and not stored.artifacts
        line = next(line for line in events if "delegation.started agent=release" in line)
        child_id = line.split("task='")[1].split("'")[0]
        keys = load_server_keys(settings.credentials_directory, "coordinator")
        child = await PeerClient(
            settings, "release", events.append, credential=keys.delegated("alice", "release")
        ).get_task(child_id)
        assert child.status.state == 5 and not child.artifacts
