# a2a-lab

An engineering lab for the Agent2Agent (A2A) protocol, reusable Python agent boilerplate, and secure delegation.

M1 and M2 are implemented. Run two independent local agents that discover each other through Agent Cards and delegate over real A2A HTTP. The knowledge agent answers from bundled synthetic engineering notes; the coordinator performs one approved lookup and composes the result. No model account or paid API key is required.

The [project constitution](docs/constitution.md) governs contributors and future coding agents. The M1 SDK probe remains available for diagnostics. Authentication, task ownership, cancellation exercises, and human approval controls follow in M3.

## Setup and foundation check

Install `uv`, then run these commands from this code repository. In the full workspace, this repository is `src/a2a-lab`.

```sh
uv sync --locked
uv run a2a-lab doctor
uv run a2a-lab check-sdk
uv run a2a-lab demo
```

The runtime is pinned to Python 3.12.13. `uv` can download it when necessary. The lock includes runtime and development dependencies. No paid API keys are required.

`doctor` validates and displays the local settings. `check-sdk` discovers the card and sends a request through the official SDK using an in-process ASGI HTTP transport. Its output identifies that transport explicitly.

## Run the two-agent demo

```sh
uv run a2a-lab demo
uv run a2a-lab demo --text "How should we design secure delegation?"
```

The supervisor reserves the configured ports, starts knowledge and coordinator in separate processes, checks their cards for readiness, and calls the coordinator over HTTP. The coordinator fetches the knowledge card, validates the required skill and configured service endpoint, then delegates once. Both agents return SDK tasks with a JSON `engineering-answer` artifact containing `answer` and `references`. The CLI prints safe event traces and the composed result after cleaning up both children.

Defaults are coordinator `http://127.0.0.1:8101` and knowledge `http://127.0.0.1:8102`. Both serve `/.well-known/agent-card.json` and `/a2a/jsonrpc`. The supervisor uses POSIX socket inheritance and is verified on macOS. Standalone commands do not require descriptor inheritance:

```sh
# Terminal 1
uv run a2a-lab serve knowledge --port 8102
# Terminal 2
uv run a2a-lab serve coordinator --port 8101
# Terminal 3
uv run a2a-lab call --agent coordinator --text "What belongs in a runbook?"
uv run a2a-lab call --agent knowledge --text "What should an Agent Card describe?"
```

Stop manually served agents with Ctrl+C. Use matching configuration in all terminals when changing ports: a `serve --port` override changes that server only. For example, set `A2A_LAB_KNOWLEDGE_PORT=8202` and `A2A_LAB_COORDINATOR_PORT=8201` in every terminal, then use the defaults of `serve knowledge`, `serve coordinator`, and `call`.

Try the [first lab exercise](labs/01-local-delegation/README.md) for card inspection, failure cases, and security review. The [M2 decision record](docs/decisions/0002-local-delegation.md) explains the tested boundaries and limitations.

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
| `A2A_LAB_PROFILE` | Only the synthetic `local-demo` profile is supported. |
| `A2A_LAB_HOST` | Only `127.0.0.1` or `::1`; the unauthenticated server cannot bind publicly through these settings. |
| `A2A_LAB_PORT` | Probe port from 1 through 65535; default 8100. |
| `A2A_LAB_COORDINATOR_PORT` | Coordinator port; default 8101. Must differ from the knowledge port. |
| `A2A_LAB_KNOWLEDGE_PORT` | Approved knowledge-agent port; default 8102. |
| `A2A_LAB_REQUEST_TIMEOUT_SECONDS` | Finite timeout from greater than 0 through 300 seconds; default 5. Bounds each body read and workflow. A client exchange has a total deadline of twice this value. |
| `A2A_LAB_MAX_INPUT_CHARACTERS` | Maximum input length from 1 through 16000 characters; default 1000. |
| `A2A_LAB_MAX_PAYLOAD_BYTES` | Inbound request and outbound request/response byte limit from 1024 through 1048576; default 65536. Independent of the text character limit. |
| `A2A_LAB_MAX_CONCURRENT_REQUESTS` | Active HTTP request and workflow execution limits per agent, from 1 through 32; default 4. |
| `A2A_LAB_STARTUP_TIMEOUT_SECONDS` | Finite readiness deadline from greater than 0 through 120 seconds; default 15. |
| `A2A_LAB_SHUTDOWN_TIMEOUT_SECONDS` | Finite graceful wait from greater than 0 through 30 seconds; default 3, followed by force-killing a remaining owned child. |

This profile uses plain HTTP without authentication and is restricted to synthetic loopback exercises. M2 validates cards and structured peer output, permits only exact configured outbound URLs, rejects redirects and compressed peer responses, and bounds bodies, concurrent work, and deadlines. The coordinator makes one peer call without retries. These controls do not authenticate another local process or establish resource ownership.

Each process has its own in-memory SDK task store; restart loses it. Stored-task retention is not bounded in M2. SDK task routes are present, but the task retrieval, cancellation, delegated cancellation, and approval teaching contracts remain M3 work. Local timeouts do not guarantee that a remote task was cancelled. Streaming, push notifications, extended cards, registries, and model integrations are not part of M2.

## Repository responsibilities

| Location | Responsibility |
| --- | --- |
| `src/a2a_lab/config.py` | Validated profile and endpoint settings. |
| `src/a2a_lab/cli.py` | Diagnostics, serve/call commands, and demo entry point. |
| `src/a2a_lab/demo.py` | Reserved sockets, readiness checks, child ownership, and cleanup. |
| `src/a2a_lab/bootstrap.py` | Wire domain workflows to A2A adapters. |
| `src/a2a_lab/agents` | Deterministic coordinator, knowledge workflow, and packaged notes. |
| `src/a2a_lab/domain` | Validated application results and the narrow knowledge-provider port. |
| `src/a2a_lab/a2a` | Typed cards, SDK lifecycle, boundary limits, discovery, and delegation. |
| `docs/constitution.md` | Project rules, Python style, contributor workflow, and OWASP agent security. |
| `docs/decisions` | Tested compatibility choices and limitations. |
| `labs/01-local-delegation` | First runnable teaching exercise. |
| `tests` | Configuration, workflows, protocol contracts, limits, and real-process integration. |

Authenticated security adapters, coding skills, and later exercises will be added in their implementation milestones. Keep SDK wire types in the A2A package and domain behavior independent of transport. Django/MCP and the supply chain sample remain optional later work.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

The tests cover the M1 foundation plus M2 discovery/delegation, structured artifacts, malformed or incompatible cards, capability mismatch, redirects, payload and concurrency limits, and deadlines. Integration tests start owned loopback servers, verify separate processes, and check cleanup after success, unavailable peers, port collisions, startup failure, timeout, and interruption. Loopback networking is required for those integration tests. They do not establish the later authenticated security profile.

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
