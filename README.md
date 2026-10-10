# a2a-lab

An engineering lab for the Agent2Agent (A2A) protocol, reusable Python agent boilerplate, and secure delegation.

M1 provides the Python foundation, validated local settings, an official SDK compatibility probe, and the [project constitution](docs/constitution.md) for contributors and future coding agents. The two-agent delegation demo starts in M2. The probe acknowledges synthetic text without using a model, tools, or delegation.

## Setup and foundation check

Install `uv`, then run these commands from this code repository. In the full workspace, this repository is `src/a2a-lab`.

```sh
uv sync --locked
uv run a2a-lab doctor
uv run a2a-lab check-sdk
```

The runtime is pinned to Python 3.12.13. `uv` can download it when necessary. The lock includes runtime and development dependencies. No paid API keys are required.

`doctor` validates and displays the local settings. `check-sdk` discovers the card and sends a request through the official SDK using an in-process ASGI HTTP transport. Its output identifies that transport explicitly.

## Run the probe over local HTTP

In one terminal:

```sh
uv run a2a-lab serve-probe
```

In another terminal with matching settings:

```sh
uv run a2a-lab check-sdk --live
```

The default endpoint is `http://127.0.0.1:8100/a2a/jsonrpc`. The card is available at [the local well-known endpoint](http://127.0.0.1:8100/.well-known/agent-card.json). Stop the server with Ctrl+C.

The probe uses A2A protocol `1.0`, JSON-RPC `SendMessage`, and the released `a2a-sdk` 1.2.2. It returns an immediate message rather than demonstrating long-running tasks. Streaming, push notifications, extended cards, and 0.3 compatibility are disabled. The [compatibility decision](docs/decisions/0001-sdk-baseline.md) records verification and the task/cancellation integration to use next.

## Configuration

Defaults work without a configuration file. To use a local file, copy `.env.example` to `.env` and edit its values. Environment variables override that file. Unknown settings in `.env` are rejected, and CLI validation errors omit input values.

| Setting | Behavior |
| --- | --- |
| `A2A_LAB_PROFILE` | Only `local-demo` is supported in M1. |
| `A2A_LAB_HOST` | Only `127.0.0.1` or `::1`; the unauthenticated server cannot bind publicly through these settings. |
| `A2A_LAB_PORT` | Port from 1 through 65535; default 8100. |
| `A2A_LAB_REQUEST_TIMEOUT_SECONDS` | Positive finite client timeout, up to 300 seconds; default 5. |
| `A2A_LAB_MAX_INPUT_CHARACTERS` | Maximum input length from 1 through 16000 characters; default 1000. |

This profile uses plain HTTP without authentication and is restricted to synthetic loopback exercises. It is not a network deployment profile. Task ownership, authenticated access, approval exercises, and broader security controls arrive in M3. Text validation is not a complete HTTP payload or resource-exhaustion defense.

## Repository responsibilities

| Location | Responsibility |
| --- | --- |
| `src/a2a_lab/config.py` | Validated profile and endpoint settings. |
| `src/a2a_lab/cli.py` | Foundation diagnostics and probe commands. |
| `src/a2a_lab/a2a` | SDK integration, typed probe card, execution, and client verification. |
| `docs/constitution.md` | Project rules, Python style, contributor workflow, and OWASP agent security. |
| `docs/decisions` | Tested compatibility choices and limitations. |
| `tests` | Configuration and SDK contract behavior. |

Domain services, two agent workflows, security adapters, coding skills, and workshop exercises will be added in their implementation milestones. Keep SDK wire types in the A2A package and separate domain behavior from transport as the lab grows. Django/MCP and the supply chain sample remain optional later work.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

The foundation tests exercise unsafe settings, configuration disclosure, actual SDK discovery/request serialization, text validation, version rejection, and changed-card routing rejection. They do not establish the later authenticated security profile.

## macOS editable import troubleshooting

If installation succeeds but this workspace reports `ModuleNotFoundError: a2a_lab`, check whether generated `.pth` files have the macOS hidden flag. Python can skip such files, preventing the editable source path from loading. Clear the flag on the generated environment files, then retry:

```sh
chflags nohidden .venv/lib/python3.12/site-packages/*.pth
```

This adjustment affects only local environment metadata; do not commit `.venv`.

If the workspace reapplies hidden flags, use a normal wheel installation instead:

```sh
uv sync --locked --no-editable --reinstall-package a2a-lab
uv run --locked --no-editable a2a-lab check-sdk
```

Use `--no-editable` on subsequent `uv run` commands in that environment. After editing source, repeat the installation command before testing so the installed wheel contains the changes.

In the full workspace, planning, guides, and presentation preparation live in the sibling `documents` folder. Those authoring materials are outside this Git repository; the setup and design rules above work from a standalone clone.
