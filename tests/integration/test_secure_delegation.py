import asyncio
import os
import re
import socket
from contextlib import ExitStack
from pathlib import Path

import pytest

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.control_client import control_request
from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.security.identity import initialize_security, load_server_keys

pytestmark = pytest.mark.skipif(
    os.name != "posix", reason="The supervisor uses POSIX socket inheritance"
)


@pytest.fixture
def secured(tmp_path: Path) -> Settings:
    directory = tmp_path / "credentials"
    initialize_security(directory)
    with ExitStack() as stack:
        listeners = [stack.enter_context(socket.socket()) for _ in range(2)]
        for listener in listeners:
            listener.bind(("127.0.0.1", 0))
        return Settings(
            _env_file=None,
            profile="local-secure",
            credentials_directory=directory,
            coordinator_port=listeners[0].getsockname()[1],
            knowledge_port=listeners[1].getsockname()[1],
            fixture_delay_seconds=0.4,
        )


async def test_real_authenticated_delegation_and_human_control(secured: Settings) -> None:
    events: list[str] = []
    alice = PeerClient(secured, "coordinator", events.append)
    bob = PeerClient(secured, "coordinator", events.append, owner="bob")
    async with running_agents(secured, events.append):
        result = await alice.call("Explain secure delegation and runbooks.")
        stored = await alice.get_task(result.task_id)
        with pytest.raises(LookupFailure):
            await bob.get_task(result.task_id)
        assert not (await bob.list_tasks()).tasks
        proposal = await control_request(
            secured,
            "alice",
            "propose",
            {
                "task_id": result.task_id,
                "artifact_id": stored.artifacts[0].artifact_id,
            },
        )
        grant = await control_request(
            secured,
            "alice",
            "approve",
            {
                "proposal_id": proposal["proposal_id"],
                "expected_digest": proposal["digest"],
                "terms": proposal["terms"],
            },
        )
        receipt = await control_request(
            secured,
            "alice",
            "execute",
            {
                "proposal_id": proposal["proposal_id"],
                "approval_id": grant["approval_id"],
                "terms": proposal["terms"],
                "idempotency_key": "simulated-human-reviewed-release",
            },
        )
        assert receipt["fixture"]["references"]
    assert any("actor=coordinator owner=alice" in event for event in events)
    assert any("actor=human-alice" in event for event in events)
    pids = [
        int(event.split("pid=")[1]) for event in events if event.startswith("supervisor.started")
    ]
    assert len(set(pids)) == 2
    for pid in pids:
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)


async def test_root_cancellation_stops_the_owned_delegated_task(secured: Settings) -> None:
    events: list[str] = []
    alice = PeerClient(secured, "coordinator", events.append)
    async with running_agents(secured, events.append):
        root = await alice.start("[slow] runbook")
        async with asyncio.timeout(3):
            while not any(
                "[knowledge pid=" in event and "workflow.started" in event for event in events
            ):
                await asyncio.sleep(0.01)
        cancelled = await alice.cancel_task(root.id)
        assert cancelled.status.state == 5
        async with asyncio.timeout(3):
            while not any("delegation.cancelled agent=knowledge" in event for event in events):
                await asyncio.sleep(0.01)
        line = next(
            event for event in events if "[knowledge pid=" in event and "workflow.started" in event
        )
        downstream_id = re.search(r"task='([^']+)'", line).group(1)
        await asyncio.sleep(0.45)
        assert (await alice.get_task(root.id)).status.state == 5
        credential = load_server_keys(secured.credentials_directory, "coordinator").delegated(
            "alice"
        )
        downstream = PeerClient(secured, "knowledge", lambda event: None, credential=credential)
        task = await downstream.get_task(downstream_id)
        assert task.status.state == 5
        assert not task.artifacts
        other_credential = load_server_keys(secured.credentials_directory, "coordinator").delegated(
            "bob"
        )
        with pytest.raises(LookupFailure):
            await PeerClient(
                secured, "knowledge", lambda event: None, credential=other_credential
            ).get_task(downstream_id)
