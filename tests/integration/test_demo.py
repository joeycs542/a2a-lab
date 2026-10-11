import asyncio
import json
import os
import signal
import socket
import sys
from contextlib import ExitStack
from pathlib import Path

import pytest

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.config import Settings
from a2a_lab.demo import DemoFailure, run_demo, running_agents

pytestmark = pytest.mark.skipif(os.name != "posix", reason="The demo uses POSIX socket inheritance")


@pytest.fixture
def settings() -> Settings:
    with ExitStack() as stack:
        listeners = [stack.enter_context(socket.socket()) for _ in range(2)]
        for listener in listeners:
            listener.bind(("127.0.0.1", 0))
        return Settings(
            _env_file=None,
            coordinator_port=listeners[0].getsockname()[1],
            knowledge_port=listeners[1].getsockname()[1],
        )


def started_pids(events: list[str]) -> list[int]:
    return [
        int(event.split("pid=")[1]) for event in events if event.startswith("supervisor.started")
    ]


def assert_stopped(events: list[str], settings: Settings) -> None:
    for pid in started_pids(events):
        with pytest.raises(ProcessLookupError):
            os.kill(pid, 0)
    for port in (settings.coordinator_port, settings.knowledge_port):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((settings.host, port))


async def test_two_independent_processes_discover_and_delegate_over_http(
    settings: Settings,
) -> None:
    events: list[str] = []
    result = await run_demo(settings, "What belongs in a runbook?", events.append)
    pids = started_pids(events)
    assert len(pids) == len(set(pids)) == 2
    assert os.getpid() not in pids
    assert result.answer.references[0].fixture_id == "runbook"
    assert result.answer.answer.startswith("Knowledge agent findings:")
    assert any(
        "[coordinator pid=" in event and "rpc.send agent=knowledge" in event for event in events
    )
    assert any("[knowledge pid=" in event and "workflow.completed" in event for event in events)
    assert len([event for event in events if event.startswith("supervisor.ready")]) == 2
    assert len([event for event in events if event.startswith("supervisor.stopped")]) == 2
    assert_stopped(events, settings)


async def test_occupied_port_does_not_start_children_or_call_existing_server(
    settings: Settings,
) -> None:
    events: list[str] = []
    with socket.socket() as occupied:
        occupied.bind((settings.host, settings.coordinator_port))
        occupied.listen()
        with pytest.raises(DemoFailure, match="reserve demo ports"):
            await run_demo(settings, "runbook", events.append)
    assert started_pids(events) == []
    assert_stopped(events, settings)


async def test_second_spawn_failure_reaps_the_first_child(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    original = asyncio.create_subprocess_exec
    attempts = 0

    async def fail_second(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            raise OSError("simulated startup failure")
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fail_second)
    with pytest.raises(DemoFailure):
        await run_demo(settings, "runbook", events.append)
    assert len(started_pids(events)) == 1
    assert_stopped(events, settings)


async def test_startup_deadline_reaps_both_children(settings: Settings) -> None:
    events: list[str] = []
    short = Settings(**{**settings.model_dump(), "startup_timeout_seconds": 0.001}, _env_file=None)
    with pytest.raises(DemoFailure, match="startup exceeded"):
        await run_demo(short, "runbook", events.append)
    assert_stopped(events, settings)


async def test_unavailable_knowledge_peer_is_controlled_and_cleanup_still_runs(
    settings: Settings,
) -> None:
    events: list[str] = []
    async with running_agents(settings, events.append):
        pid = next(
            int(event.split("pid=")[1])
            for event in events
            if event.startswith("supervisor.started agent=knowledge")
        )
        os.kill(pid, signal.SIGTERM)
        await asyncio.sleep(0.1)
        with pytest.raises(LookupFailure):
            await PeerClient(settings, "coordinator", events.append).call("runbook")
    assert_stopped(events, settings)


async def test_cli_interrupt_stops_owned_children(settings: Settings, tmp_path: Path) -> None:
    environment = dict(os.environ)
    environment.update(
        {
            f"A2A_LAB_{key.upper()}": (
                json.dumps(value) if isinstance(value, (list, dict)) else str(value)
            )
            for key, value in settings.model_dump(mode="json").items()
        }
    )
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "a2a_lab",
        "demo",
        cwd=tmp_path,
        env=environment,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    events: list[str] = []
    try:
        async with asyncio.timeout(15):
            assert process.stdout is not None
            while len(started_pids(events)) < 2:
                line = await process.stdout.readline()
                assert line, "Demo exited before starting both children"
                events.append(line.decode().strip())
            process.send_signal(signal.SIGINT)
            stdout, stderr = await process.communicate()
        events.extend(stdout.decode().splitlines())
        assert process.returncode == 130
        assert "owned demo servers have been stopped" in stderr.decode()
        assert_stopped(events, settings)
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
