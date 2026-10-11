# a2a-lab

An engineering lab for the Agent2Agent (A2A) protocol, reusable Python agent boilerplate, and secure delegation.

M1 through M3 are implemented. Run two independent local agents that discover each other through Agent Cards and delegate over real A2A HTTP. The knowledge agent answers from bundled synthetic engineering notes; the coordinator performs one approved lookup and composes the result. The authenticated profile adds owner-scoped tasks, cancellation, and a separate human approval exercise. No model account or paid API key is required.

The [project constitution](docs/constitution.md) governs contributors and future coding agents. The M1 SDK probe and original unauthenticated loopback demo remain available. Coding agent skills and the reusable extension exercise follow in M4.

## Run with Docker

Use Docker Desktop and Compose to run the lab without a host Python environment:

```sh
docker compose up --build -d --wait
docker compose run --rm client call
docker compose logs coordinator knowledge
```

The default is the authenticated M3 profile. Each agent runs in its own container;
they communicate through a shared private loopback network namespace. No ports
are published to the host. The client container performs discovery and A2A calls
in that namespace. Dependencies are installed from `uv.lock` into the image;
there are no source, `.venv`, `.env`, or host-credential mounts. The first image
build downloads base images and dependencies; later calls reuse the running agents.

Private teaching credentials live in three separate Docker volumes. Only the
initialization job accesses all three; each agent mounts its own authority read-only,
and the operator client holds the simulated user/human accounts. Follow the
[Docker lab](labs/02-docker-delegation/README.md) for task commands, the optional
unauthenticated profile, human approval, restart/expiry behavior, and teardown.

## Host Python setup and foundation check

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

## Run the authenticated local profile

Generate private teaching credentials once, then run the supervised demo:

```sh
uv run a2a-lab init-security
uv run a2a-lab demo --secure
```

Credentials are generated under `.runtime/security`, which is ignored by Git. Files use mode 0600 in a private directory, values are not printed, and existing credentials are never overwritten. Their default lifetime is one hour. To rotate them, generate a new directory with `init-security --directory`, set `A2A_LAB_CREDENTIALS_DIRECTORY` to its absolute path, and restart both servers with that setting.

For manual serving and task commands, set `A2A_LAB_PROFILE=local-secure` in every terminal. The CLI operator holds the synthetic Alice and Bob accounts; `--as bob` selects Bob's credential. The coordinator instead holds only its outbound knowledge-service credentials, bound to the verified represented user. It does not forward the caller's token. Human-control credentials are distinct and cannot make A2A calls.

```sh
export A2A_LAB_PROFILE=local-secure
uv run a2a-lab serve knowledge
# In another terminal with the same profile:
uv run a2a-lab serve coordinator
# In a third terminal with the same profile:
uv run a2a-lab call --async --text "[slow] What belongs in a runbook?"
uv run a2a-lab task get TASK_ID
uv run a2a-lab task cancel TASK_ID
uv run a2a-lab task get TASK_ID --as bob
```

Replace `TASK_ID` with the returned ID. Alice can retrieve and cancel her own task; Bob is denied. `[slow]` delays the knowledge fixture by the configured duration; `[fail]` produces a controlled failed task. The authenticated coordinator tracks its delegated task and attempts cancellation when interrupted or out of budget. Cancellation is verified over live HTTP for the supplied cooperative workflows; an unavailable peer or lost start response can still leave the remote outcome unknown.

Follow [Lab 3](labs/03-secure-delegation/README.md) for the exact-term proposal, human approval, and single-release exercise. Its fixed destination is a local JSON display receipt, not procurement or external publication. The [M3 decision record](docs/decisions/0003-authenticated-lifecycle.md) describes identity scopes, cancellation ordering, approval integrity, and the tested limits.

Both profiles bind only to loopback. `local-secure` teaches caller authentication and application authorization; it does not provide TLS, signed server identity, OS process isolation, or an external identity provider. The operator can simulate all teaching accounts because it holds their credentials.

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
| `A2A_LAB_PROFILE` | `local-demo` is the unauthenticated default; `local-secure` uses generated recipient-bound credentials. |
| `A2A_LAB_HOST` | Only `127.0.0.1` or `::1`; both profiles are restricted to loopback. |
| `A2A_LAB_PORT` | Probe port from 1 through 65535; default 8100. |
| `A2A_LAB_COORDINATOR_PORT` | Coordinator port; default 8101. Must differ from the knowledge port. |
| `A2A_LAB_KNOWLEDGE_PORT` | Approved knowledge-agent port; default 8102. |
| `A2A_LAB_REQUEST_TIMEOUT_SECONDS` | Finite timeout from greater than 0 through 300 seconds; default 5. Bounds each body read and workflow. A client exchange has a total deadline of twice this value. |
| `A2A_LAB_MAX_INPUT_CHARACTERS` | Maximum input length from 1 through 16000 characters; default 1000. |
| `A2A_LAB_MAX_PAYLOAD_BYTES` | Inbound request and outbound request/response byte limit from 1024 through 1048576; default 65536. Independent of the text character limit. |
| `A2A_LAB_MAX_CONCURRENT_REQUESTS` | Active HTTP request and workflow execution limits per agent, from 1 through 32; default 4. |
| `A2A_LAB_STARTUP_TIMEOUT_SECONDS` | Finite readiness deadline from greater than 0 through 120 seconds; default 15. |
| `A2A_LAB_SHUTDOWN_TIMEOUT_SECONDS` | Finite graceful wait from greater than 0 through 30 seconds; default 3, followed by force-killing a remaining owned child. |
| `A2A_LAB_CREDENTIALS_DIRECTORY` | Private generated configuration; default `.runtime/security`, resolved to an absolute path. |
| `A2A_LAB_FIXTURE_DELAY_SECONDS` | Delay for `[slow]` requests from 0 through 60 seconds; default 2. |
| `A2A_LAB_MAX_TASK_POLLS` | Poll budget from 1 through 1000; default 100. One send, bounded reads, and no send retries. |
| `A2A_LAB_MAX_RETAINED_TASKS` | Global retained-task cap per agent from 1 through 10000; default 128. At capacity, new records are rejected. |
| `A2A_LAB_MAX_APPROVAL_RECORDS` | Cap for each proposal/grant/receipt collection from 1 through 10000; default 128. |

The required demo uses synthetic loopback HTTP. Both profiles validate cards and structured peer output, permit only exact configured outbound URLs, reject redirects and compressed peer responses, and bound bodies, concurrency, time, and retained records. The authenticated profile enforces identity, role, and resource ownership on each request. A credential or card cannot widen the configured peer destinations. Best-effort cancellation cleanup has an additional one-second maximum client budget.

Each process has its own bounded in-memory SDK task store; restart loses it. Tasks are scoped by acting identity and represented user in `local-secure`; `local-demo` has a shared anonymous scope. Task retrieval, listing, and cancellation use the SDK. Completed tasks cannot be continued through the lab API. Proposal, approval, and receipt state is also bounded and ephemeral; record caps reject new work without discarding replay evidence. Streaming, push notifications, extended cards, registries, and model integrations remain outside the implemented lab.

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
| `src/a2a_lab/security` | Recipient-bound identity, explicit HTTP permissions, and atomic synthetic approval/release state. |
| `docs/constitution.md` | Project rules, Python style, contributor workflow, and OWASP agent security. |
| `docs/decisions` | Tested compatibility choices and limitations. |
| `labs/01-local-delegation` | First runnable teaching exercise. |
| `labs/03-secure-delegation` | Authenticated task lifecycle and exact human approval exercise. |
| `tests` | Configuration, workflows, protocol contracts, limits, and real-process integration. |

Coding skills and later exercises will be added in their implementation milestones. Keep SDK wire types in the A2A package and domain behavior independent of transport. Django/MCP and the supply chain sample remain optional later work.

Local model integration guidance is planned for M4/M5: choosing a runtime and model for the available hardware, local serving, adapter wiring, output validation, and security/evaluation checks. A model adapter will connect behind an application interface while preserving A2A and policy boundaries. Actual model integration remains optional; the current agents use fixtures and have no downloaded models.

## Verification

```sh
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Tests cover configuration, discovery/delegation, typed artifacts, unsafe cards/destinations, payload and concurrency limits, deadlines, and owned-process cleanup. M3 adds invalid/expired/wrong-recipient credentials, owner-scoped results and cancellation, delegated identity, late-result prevention, polling/retention budgets, and missing/changed/expired/concurrent/replayed approvals. Live HTTP tests verify authenticated delegation, downstream cancellation, and the synthetic release flow. These are deterministic policy checks; they do not evaluate an LLM's resistance to prompt injection. Loopback networking is required for integration tests.

## macOS environment troubleshooting

### Repair a slow or offloaded environment

If the CLI pauses before printing its first event, inspect the environment files:

```sh
ls -lO .venv/lib/python3.12/site-packages/a2a/server/agent_execution
```

Files marked `dataless` have no locally resident contents. Reading them can stall
Python imports while macOS retrieves their data. The normal fixture does not
intentionally delay; only `[slow]` adds a delay. The project configures uv's
[copy installation mode](https://docs.astral.sh/uv/reference/settings/#link-mode)
so installed package files are independent of its cache.

**For an iCloud Drive folder, select the outer `a2a-lab` folder in Finder and
enable Keep Downloaded. Wait for downloads to finish before retrying.** Reinstalling
with uv does not prevent iCloud from offloading those files afterward; this was
observed even after a successful clean reinstall. Docker avoids host dependency
imports and host credential reads; its initial build still needs the small source
files available locally.

Repair an existing environment from the unchanged lockfile, bypassing cached
packages. If you previously set an external environment path, clear it first:

```sh
unset UV_PROJECT_ENVIRONMENT
uv sync --locked --reinstall --no-cache
uv run --locked a2a-lab demo
```

If replacing the old packages also stalls, stop the reinstall and preserve the
generated environment within the ignored runtime directory, then create a fresh
standard `.venv`. Stop any agents using that environment first, and choose an
unused backup name if one already exists:

```sh
mkdir -p .runtime
mv .venv .runtime/venv-before-repair
uv sync --locked --no-cache
uv run --locked a2a-lab demo
```

Neither procedure changes the lockfile, teaching credentials, or source code.
Subsequent commands use the normal `uv sync` and `uv run` workflow. Copy mode
does not control macOS storage policies; if files become `dataless` again, inspect
the folder's storage/sync settings. The authenticated demo still requires valid
credentials from `init-security`.

The [local installation decision](docs/decisions/0004-local-environment-installation.md)
records the repair, demo timings, verification, and limits.

### Editable imports

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
