"""Commands for diagnostics, independent agents, and supervised delegation."""

import argparse
import asyncio
import json
import platform
import socket
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import httpx
import uvicorn
from google.protobuf.json_format import MessageToDict
from pydantic import ValidationError

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.a2a.control_client import control_request
from a2a_lab.a2a.directory import DirectoryClient
from a2a_lab.a2a.probe import create_probe_app, verify_in_process, verify_sdk
from a2a_lab.bootstrap import build_app
from a2a_lab.config import Settings
from a2a_lab.demo import DEFAULT_QUESTION, DemoFailure, run_demo
from a2a_lab.domain.discovery import SearchRequest, topic_scores
from a2a_lab.domain.roles import AGENTS, services_for
from a2a_lab.security.approval import (
    ApprovalRequest,
    ExecutionRequest,
    Grant,
    Proposal,
    ReleaseTerms,
)
from a2a_lab.security.identity import SecurityError, initialize_security
from a2a_lab.web.server import create_web_app


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
    commands.add_parser("serve-web", help="Run the local operator browser interface")
    commands.add_parser("serve-probe", help="Run the loopback-only M1 SDK probe")
    check = commands.add_parser("check-sdk", help="Resolve and invoke the SDK compatibility probe")
    check.add_argument("--live", action="store_true", help="Call a running serve-probe over HTTP")
    serve = commands.add_parser("serve", help="Run an independent local agent")
    serve.add_argument("agent", choices=services_for("discovery"))
    serve.add_argument("--port", type=int, help="Override this agent's configured port")
    serve.add_argument("--socket-fd", type=int, help=argparse.SUPPRESS)
    call = commands.add_parser("call", help="Discover and call a running approved agent")
    call.add_argument("--agent", choices=AGENTS, default="coordinator")
    call.add_argument("--text", default=DEFAULT_QUESTION)
    call.add_argument("--as", choices=["alice", "bob"], dest="owner", default="alice")
    call.add_argument(
        "--async", action="store_true", dest="background", help="Start a task and return its ID"
    )
    demo = commands.add_parser("demo", help="Start the selected agents, delegate, and stop them")
    demo.add_argument("--text", default=DEFAULT_QUESTION)
    demo.add_argument("--secure", action="store_true", help="Use generated local credentials")
    demo.add_argument("--discovery", action="store_true", help="Run authenticated catalog routing")
    discover = commands.add_parser(
        "discover", help="Search approved catalog and validate live cards"
    )
    discover.add_argument("--text", default=DEFAULT_QUESTION)
    discover.add_argument("--as", choices=["alice", "bob"], dest="owner", default="alice")
    initialize = commands.add_parser(
        "init-security", help="Create private local teaching credentials"
    )
    initialize.add_argument("--directory", type=Path)
    initialize.add_argument("--discovery", action="store_true")
    initialize.add_argument("--ttl-seconds", type=int, default=3600)
    tasks = commands.add_parser("task", help="Retrieve, list, or cancel agent tasks")
    tasks.add_argument("operation", choices=["get", "list", "cancel"])
    tasks.add_argument("task_id", nargs="?")
    tasks.add_argument("--agent", choices=AGENTS, default="coordinator")
    tasks.add_argument("--as", choices=["alice", "bob"], dest="owner", default="alice")
    action = commands.add_parser(
        "action", help="Propose, explicitly approve, or execute a synthetic fixture release"
    )
    action.add_argument("operation", choices=["propose", "approve", "execute"])
    action.add_argument("--as", choices=["alice", "bob"], dest="owner", default="alice")
    action.add_argument("--task-id")
    action.add_argument("--artifact-id")
    action.add_argument("--label", default="Teaching fixture")
    action.add_argument("--proposal-file", type=Path)
    action.add_argument("--approval-file", type=Path)
    action.add_argument("--idempotency-key")
    action.add_argument(
        "--confirm", action="store_true", help="Explicitly approve the reviewed proposal"
    )
    action.add_argument("--ttl-seconds", type=int, default=60)
    args = parser.parse_args(argv)

    try:
        overrides = (
            {f"{args.agent}_port": args.port}
            if args.command == "serve" and args.port is not None
            else {}
        )
        if args.command == "demo" and args.secure:
            overrides["profile"] = "local-secure"
        if args.command in {"demo", "init-security"} and args.discovery:
            overrides.update(topology="discovery", profile="local-secure")
        settings = Settings(**overrides)
    except ValidationError as error:
        print("Invalid lab configuration:", file=sys.stderr)
        for issue in error.errors(include_input=False, include_url=False):
            field = ".".join(str(part) for part in issue["loc"])
            print(f"  {field}: {issue['msg']}", file=sys.stderr)
        return 2

    if args.command == "init-security":
        try:
            initialize_security(
                args.directory or settings.credentials_directory,
                args.ttl_seconds,
                topology=settings.topology,
            )
        except (SecurityError, OSError) as error:
            print(
                f"Could not create new credentials ({type(error).__name__}). "
                "Existing files are preserved.",
                file=sys.stderr,
            )
            return 1
        print("Private local credentials created; their values are not displayed.")
    elif args.command == "doctor":
        print(
            json.dumps(
                {
                    "python": platform.python_version(),
                    "sdk_version": version("a2a-sdk"),
                    "settings": settings.model_dump(mode="json"),
                    "endpoint": settings.rpc_url,
                    "scope": "Synthetic loopback profile; not a network deployment.",
                },
                indent=2,
            )
        )
    elif args.command == "serve-web":
        try:
            app = create_web_app(settings)
        except (SecurityError, ValueError, OSError):
            print(
                "Browser configuration unavailable; use authenticated discovery credentials.",
                file=sys.stderr,
            )
            return 2
        uvicorn.run(
            app,
            host="0.0.0.0" if settings.web_bind == "container" else settings.host,
            port=settings.web_port,
            log_level="warning",
        )
    elif args.command == "serve-probe":
        if settings.profile != "local-demo":
            print("The M1 compatibility probe requires local-demo.", file=sys.stderr)
            return 2
        uvicorn.run(
            create_probe_app(settings), host=settings.host, port=settings.port, log_level="warning"
        )
    elif args.command == "serve":
        port = settings.service_port(args.agent)
        if args.socket_fd is not None and not _validate_listener(args.socket_fd, settings, port):
            print(
                "Invalid supervised listener; it must match the configured loopback endpoint.",
                file=sys.stderr,
            )
            return 2
        try:
            app = build_app(args.agent, settings)
        except (SecurityError, ValidationError, OSError):
            print(
                "Secure configuration unavailable; generate valid private credentials first.",
                file=sys.stderr,
            )
            return 2
        uvicorn.run(
            app,
            host=settings.host,
            port=port,
            fd=args.socket_fd,
            log_level="warning",
            timeout_graceful_shutdown=int(settings.shutdown_timeout_seconds),
        )
    elif args.command == "discover":

        def discovery_trace(event: str) -> None:
            print(event, flush=True)

        async def inspect() -> dict[str, object]:
            if settings.topology != "discovery":
                raise SecurityError("Search requires the discovery topology.")
            if not args.text.strip() or len(args.text) > settings.max_input_characters:
                raise LookupFailure("Text is empty or exceeds the configured limit.")
            topics = tuple(
                topic
                for topic, score in topic_scores(args.text, settings.demo_scenario).items()
                if score
            )
            if not topics:
                return {"candidates": [], "reason": "no-supported-topic"}
            async with asyncio.timeout(settings.request_timeout_seconds):
                result = await DirectoryClient(settings, discovery_trace, owner=args.owner).search(
                    SearchRequest(topics=topics)
                )
                candidates: list[dict[str, object]] = []
                for candidate in result.candidates:
                    try:
                        await PeerClient(
                            settings, candidate.peer_id, discovery_trace, owner=args.owner
                        ).discover()
                        viable = True
                    except LookupFailure:
                        viable = False
                    candidates.append(
                        {
                            "peer_id": candidate.peer_id,
                            "skill_id": candidate.skill_id,
                            "viable": viable,
                        }
                    )
                return {"candidates": candidates}

        try:
            print(json.dumps(asyncio.run(inspect()), indent=2))
        except (LookupFailure, SecurityError, TimeoutError):
            print("Discovery unavailable or outside approved policy.", file=sys.stderr)
            return 1
    elif args.command in {"call", "demo"}:

        def trace(event: str) -> None:
            print(event, flush=True)

        try:
            if args.command == "demo":
                result = asyncio.run(run_demo(settings, args.text, trace))
            elif args.background:
                task = asyncio.run(
                    PeerClient(settings, args.agent, trace, owner=args.owner).start(args.text)
                )
                print(json.dumps(MessageToDict(task), indent=2))
                return 0
            else:
                result = asyncio.run(
                    PeerClient(settings, args.agent, trace, owner=args.owner).call(args.text)
                )
        except (LookupFailure, DemoFailure, SecurityError) as error:
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
    elif args.command == "task":
        if args.operation != "list" and not args.task_id:
            parser.error("task get/cancel requires a task ID")
        client = PeerClient(settings, args.agent, lambda event: None, owner=args.owner)
        try:
            if args.operation == "list":
                listing = asyncio.run(client.list_tasks())
                payload = MessageToDict(listing)
            elif args.operation == "get":
                payload = MessageToDict(asyncio.run(client.get_task(args.task_id)))
            else:
                payload = MessageToDict(asyncio.run(client.cancel_task(args.task_id)))
        except (LookupFailure, SecurityError):
            print("Task operation denied or unavailable.", file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2))
    elif args.command == "action":
        try:
            if args.operation == "propose":
                if not args.task_id or not args.artifact_id:
                    parser.error("action propose requires task and artifact IDs")
                data = ReleaseTerms(
                    task_id=args.task_id, artifact_id=args.artifact_id, label=args.label
                ).model_dump(mode="json")
            else:
                if args.proposal_file is None:
                    parser.error("action approve/execute requires --proposal-file")
                proposal = Proposal.model_validate_json(
                    args.proposal_file.read_text(encoding="utf-8")
                )
                if args.operation == "approve":
                    if not args.confirm:
                        parser.error("Review the exact proposal before approving with --confirm")
                    data = ApprovalRequest(
                        proposal_id=proposal.proposal_id,
                        expected_digest=proposal.digest,
                        terms=proposal.terms,
                        ttl_seconds=args.ttl_seconds,
                    ).model_dump(mode="json")
                else:
                    if args.approval_file is None or not args.idempotency_key:
                        parser.error(
                            "action execute requires --approval-file and --idempotency-key"
                        )
                    grant = Grant.model_validate_json(
                        args.approval_file.read_text(encoding="utf-8")
                    )
                    data = ExecutionRequest(
                        proposal_id=proposal.proposal_id,
                        approval_id=grant.approval_id,
                        terms=proposal.terms,
                        idempotency_key=args.idempotency_key,
                    ).model_dump(mode="json")
            payload = asyncio.run(control_request(settings, args.owner, args.operation, data))
        except (SecurityError, ValidationError, OSError, httpx.HTTPError):
            print("Action denied, unavailable, or invalid for these exact terms.", file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2))
    elif args.command == "check-sdk":
        if settings.profile != "local-demo":
            print("The M1 compatibility probe requires local-demo.", file=sys.stderr)
            return 2
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
