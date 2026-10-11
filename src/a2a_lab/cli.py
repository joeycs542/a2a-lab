"""Commands for diagnostics, independent agents, and supervised delegation."""

import argparse
import asyncio
import json
import platform
import socket
import sys
from collections.abc import Sequence
from importlib.metadata import version

import uvicorn
from pydantic import ValidationError

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.probe import create_probe_app, verify_in_process, verify_sdk
from a2a_lab.bootstrap import build_app
from a2a_lab.config import Settings
from a2a_lab.demo import DEFAULT_QUESTION, DemoFailure, run_demo


def _validate_listener(fd: int, settings: Settings, port: int) -> bool:
    try:
        family = socket.AF_INET6 if settings.host == "::1" else socket.AF_INET
        with socket.fromfd(fd, family, socket.SOCK_STREAM) as listener:
            address = listener.getsockname()
            return (
                isinstance(address, tuple)
                and address[0] == settings.host
                and address[1] == port
                and listener.getsockopt(socket.SOL_SOCKET, socket.SO_TYPE) == socket.SOCK_STREAM
            )
    except OSError:
        return False


def main(argv: Sequence[str] | None = None) -> int:
    """Validate settings, dispatch a command, and report safe failures."""
    parser = argparse.ArgumentParser(description="Local A2A engineering lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Validate and display the synthetic local configuration")
    commands.add_parser("serve-probe", help="Run the loopback-only M1 SDK probe")
    check = commands.add_parser("check-sdk", help="Resolve and invoke the SDK compatibility probe")
    check.add_argument("--live", action="store_true", help="Call a running serve-probe over HTTP")
    serve = commands.add_parser("serve", help="Run an independent local agent")
    serve.add_argument("agent", choices=["coordinator", "knowledge"])
    serve.add_argument("--port", type=int, help="Override this agent's configured port")
    serve.add_argument("--socket-fd", type=int, help=argparse.SUPPRESS)
    call = commands.add_parser("call", help="Discover and call a running approved agent")
    call.add_argument("--agent", choices=["coordinator", "knowledge"], default="coordinator")
    call.add_argument("--text", default=DEFAULT_QUESTION)
    demo = commands.add_parser("demo", help="Start both agents, delegate over HTTP, and stop them")
    demo.add_argument("--text", default=DEFAULT_QUESTION)
    args = parser.parse_args(argv)

    try:
        overrides = (
            {f"{args.agent}_port": args.port}
            if args.command == "serve" and args.port is not None
            else {}
        )
        settings = Settings(**overrides)
    except ValidationError as error:
        print("Invalid lab configuration:", file=sys.stderr)
        for issue in error.errors(include_input=False, include_url=False):
            field = ".".join(str(part) for part in issue["loc"])
            print(f"  {field}: {issue['msg']}", file=sys.stderr)
        return 2

    if args.command == "doctor":
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "sdk_version": version("a2a-sdk"),
                    "settings": settings.model_dump(),
                    "endpoint": settings.rpc_url,
                    "scope": "Synthetic loopback use; no authentication or network deployment.",
                },
                indent=2,
            )
        )
    elif args.command == "serve-probe":
        uvicorn.run(
            create_probe_app(settings), host=settings.host, port=settings.port, log_level="warning"
        )
    elif args.command == "serve":
        port = settings.coordinator_port if args.agent == "coordinator" else settings.knowledge_port
        if args.socket_fd is not None and not _validate_listener(args.socket_fd, settings, port):
            print(
                "Invalid supervised listener; it must match the configured loopback endpoint.",
                file=sys.stderr,
            )
            return 2
        uvicorn.run(
            build_app(args.agent, settings),
            host=settings.host,
            port=port,
            fd=args.socket_fd,
            log_level="warning",
            timeout_graceful_shutdown=int(settings.shutdown_timeout_seconds),
        )
    elif args.command in {"call", "demo"}:

        def trace(event: str) -> None:
            print(event, flush=True)

        try:
            if args.command == "demo":
                result = asyncio.run(run_demo(settings, args.text, trace))
            else:
                result = asyncio.run(PeerClient(settings, args.agent, trace).call(args.text))
        except (LookupFailure, DemoFailure) as error:
            print(str(error), file=sys.stderr)
            return 1
        except KeyboardInterrupt:
            print("Interrupted; owned demo servers have been stopped.", file=sys.stderr)
            return 130
        print(
            json.dumps(
                {"task_id": result.task_id, **result.answer.model_dump(mode="json")}, indent=2
            )
        )
    elif args.command == "check-sdk":
        try:
            if args.live:
                report = asyncio.run(verify_sdk(settings))
                report["transport"] = "loopback HTTP"
            else:
                report = asyncio.run(verify_in_process(settings))
        except Exception as error:
            print(f"SDK compatibility check failed ({type(error).__name__}).", file=sys.stderr)
            if args.live:
                print("Start serve-probe with matching settings before --live.", file=sys.stderr)
            return 1
        print(json.dumps(report, indent=2))
    return 0
