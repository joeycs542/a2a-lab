"""Own the local servers, their reserved sockets, and bounded startup."""

import asyncio
import json
import os
import socket
import sys
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager, suppress
from tempfile import TemporaryDirectory

import httpx
from a2a.client import A2ACardResolver
from a2a.client.errors import AgentCardResolutionError

from a2a_lab.a2a.client import CallResult, PeerClient, TraceSink, validate_card
from a2a_lab.a2a.limits import BoundedTransport
from a2a_lab.config import Settings
from a2a_lab.domain.roles import ServiceName, services_for

DEFAULT_QUESTION = "What information should our service runbook contain?"


class DemoFailure(RuntimeError):
    """Startup or shutdown could not meet the supervised demo contract."""


async def _read_trace(process: asyncio.subprocess.Process, trace: TraceSink) -> None:
    if process.stdout is None:
        return
    async for line in process.stdout:
        text = line.decode("utf-8", errors="replace").rstrip()
        if text.startswith(tuple(f"[{service} pid=" for service in services_for("discovery"))):
            trace(text[:1024])


async def _stop(process: asyncio.subprocess.Process, timeout: float) -> None:
    if process.returncode is not None:
        await process.wait()
        return
    with suppress(ProcessLookupError):
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout)
    except TimeoutError:
        with suppress(ProcessLookupError):
            process.kill()
        await process.wait()


async def _wait_ready(
    processes: dict[ServiceName, asyncio.subprocess.Process], settings: Settings, trace: TraceSink
) -> None:
    urls = frozenset(
        f"{settings.agent_base_url(agent)}"
        + ("/health" if agent == "directory" else "/.well-known/agent-card.json")
        for agent in processes
    )
    async with (
        asyncio.timeout(settings.startup_timeout_seconds),
        httpx.AsyncClient(
            transport=BoundedTransport(urls, settings.max_payload_bytes),
            timeout=min(0.5, settings.request_timeout_seconds),
            trust_env=False,
            follow_redirects=False,
            headers={"Accept-Encoding": "identity"},
        ) as client,
    ):
        for agent, process in processes.items():
            while True:
                if process.returncode is not None:
                    raise DemoFailure(f"The {agent} server exited during startup.")
                try:
                    if agent == "directory":
                        response = await client.get(f"{settings.agent_base_url(agent)}/health")
                        response.raise_for_status()
                        if response.json() != {"status": "ok"}:
                            raise DemoFailure("Directory health response is invalid.")
                    else:
                        card = await A2ACardResolver(
                            client, settings.agent_base_url(agent)
                        ).get_agent_card()
                        validate_card(card, agent, settings)
                    trace(f"supervisor.ready agent={agent} pid={process.pid}")
                    break
                except (AgentCardResolutionError, httpx.HTTPError):
                    await asyncio.sleep(0.05)


@asynccontextmanager
async def running_agents(settings: Settings, trace: TraceSink) -> AsyncIterator[None]:
    """Reserve both ports before spawning; always stop and reap owned children.

    Socket inheritance makes readiness belong to these children, avoiding
    accidental calls to an existing server. This supervisor requires POSIX.
    Standalone serve/call commands do not use descriptor inheritance.
    """
    if os.name != "posix":
        raise DemoFailure("The supervisor requires POSIX; use standalone serve and call commands.")
    processes: dict[ServiceName, asyncio.subprocess.Process] = {}
    readers: list[asyncio.Task[None]] = []
    with ExitStack() as stack:
        temporary = stack.enter_context(TemporaryDirectory(prefix="a2a-lab-demo-"))
        sockets: dict[ServiceName, socket.socket] = {}
        try:
            for agent in services_for(settings.topology):
                family = socket.AF_INET6 if settings.host == "::1" else socket.AF_INET
                listener = stack.enter_context(socket.socket(family, socket.SOCK_STREAM))
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                port = settings.service_port(agent)
                listener.bind((settings.host, port))
                listener.listen(128)
                sockets[agent] = listener
            environment = {
                key: value for key, value in os.environ.items() if not key.startswith("A2A_LAB_")
            }
            environment.update(
                {
                    f"A2A_LAB_{key.upper()}": (
                        json.dumps(value) if isinstance(value, (list, dict)) else str(value)
                    )
                    for key, value in settings.model_dump(mode="json").items()
                }
            )
            for agent, listener in sockets.items():
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-m",
                    "a2a_lab",
                    "serve",
                    agent,
                    "--socket-fd",
                    str(listener.fileno()),
                    cwd=temporary,
                    env=environment,
                    pass_fds=(listener.fileno(),),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    limit=16384,
                )
                processes[agent] = process
                readers.append(asyncio.create_task(_read_trace(process, trace)))
                trace(f"supervisor.started agent={agent} pid={process.pid}")
                listener.close()
            await _wait_ready(processes, settings, trace)
            yield
        except TimeoutError as error:
            raise DemoFailure("Server startup exceeded the configured deadline.") from error
        except OSError as error:
            raise DemoFailure("Could not reserve demo ports or start the local servers.") from error
        finally:
            for agent, process in reversed(processes.items()):
                await _stop(process, settings.shutdown_timeout_seconds)
                trace(f"supervisor.stopped agent={agent} pid={process.pid}")
            for reader in readers:
                if not reader.done():
                    reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)


async def run_demo(settings: Settings, question: str, trace: TraceSink) -> CallResult:
    """Run a real two-hop HTTP exchange and clean up before returning."""
    async with running_agents(settings, trace):
        return await PeerClient(settings, "coordinator", trace).call(question)
