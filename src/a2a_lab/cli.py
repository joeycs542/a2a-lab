"""Commands for the M1 foundation and compatibility probe."""

import argparse
import asyncio
import json
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import version

import uvicorn
from pydantic import ValidationError

from a2a_lab.a2a.probe import create_probe_app, verify_in_process, verify_sdk
from a2a_lab.config import Settings


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A2A engineering lab M1 foundation")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Validate and display the synthetic local configuration")
    commands.add_parser("serve-probe", help="Run the loopback-only M1 SDK probe")
    check = commands.add_parser("check-sdk", help="Resolve and invoke the SDK compatibility probe")
    check.add_argument("--live", action="store_true", help="Call a running serve-probe over HTTP")
    args = parser.parse_args(argv)

    try:
        settings = Settings()
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
    else:
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
