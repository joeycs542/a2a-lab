# M1 Python and A2A SDK baseline

Date: 11 October 2026  
Status: Accepted for the M1 foundation

Use Python 3.12.13 and released `a2a-sdk[http-server]` 1.2.2 for A2A protocol `1.0` over JSON-RPC. Use Starlette for the thin ASGI application and Uvicorn for the local server. Pin direct runtime dependencies and the build backend; retain the runtime/development lockfile.

| Component | Tested baseline |
| --- | --- |
| Python | 3.12.13, macOS ARM64. |
| Official SDK | `a2a-sdk` 1.2.2 with `http-server` extra. |
| A2A wire version and binding | `1.0`, `JSONRPC`. |
| Application version | `a2a-lab` 0.1.0. |
| HTTP integration | Starlette 1.7.0, Uvicorn 0.54.0, HTTPX 0.28.1. |
| Configuration | Pydantic Settings 2.15.0. |
| Build backend | Hatchling 1.32.4. |

The [published SDK release](https://pypi.org/project/a2a-sdk/1.2.2/) is the dependency source. The intended protocol baseline is the [A2A 1.0.0 specification](https://a2a-protocol.org/v1.0.0/specification/). Additional Python minor versions, platforms, transports, and protocol versions are not established by this verification.

## SDK integration choices

Use the SDK's protobuf-backed `AgentCard`, `AgentInterface`, `Message`, and `SendMessageRequest` types. Python constructors use snake case; the SDK owns JSON serialization. Avoid copying earlier 0.3 examples based on different card fields, part discriminators, or `message/send` method names.

Create card and JSON-RPC routes using `create_agent_card_routes` and `create_jsonrpc_routes`. The public `DefaultRequestHandler` resolves to the release's V2 handler. Use its in-memory task store and close the handler in the ASGI lifespan so work can drain on shutdown. Enable input-mode validation explicitly.

Resolve cards with `A2ACardResolver` and invoke requests with `ClientFactory`. The compatibility check validates the discovered interface against the configured endpoint, binding, and version before calling it. HTTP clients do not follow redirects or inherit proxy settings.

SDK inspection and a failing version test showed its default guard compares major versions, accepting `1.1` at a `1.0` route. The lab's narrow call-context builder restricts requests to the tested major/minor and lets the SDK generate `VersionNotSupportedError` responses. Missing, malformed, `0.3`, and `1.1` headers are rejected. Patch numbers do not affect compatibility; the client emits canonical `1.0`. No SDK code is patched and no second wire schema is introduced.

## Verification evidence

The final M1 checks passed:

- 27 configuration and SDK contract tests.
- Ruff lint and formatting checks, plus strict mypy checks for the five source modules.
- Typed card discovery and a request through the official SDK client over in-process ASGI HTTP serialization.
- A real loopback HTTP exchange with the probe in a separate server process; the temporary server stopped afterward.
- A locked, non-editable wheel installation in a separate clean environment. Its command ran from outside the repository and imported the installed package rather than the source directory.
- Configuration diagnostics reported the pinned Python/SDK baseline and explicit synthetic profile.

The tests include the actual outbound `A2A-Version: 1.0` header, unsupported input and versions, patch-version semantics, changed-card endpoint rejection before an RPC call, and configuration errors that omit input values.

## Task and cancellation integration for later milestones

The release's `AgentExecutor` interface provides `execute` and `cancel`. `TaskUpdater` publishes task status and artifact events. The V2 handler uses its active-task registry to manage executions; the cancel path stops the running execution and invokes the executor cancellation hook. Its `aclose` method drains active work.

These lifecycle APIs were inspected in the installed release. The M1 executor returns an immediate message and has no long-running cancellable operation. Runtime task retrieval, cancellation races, delegated cancellation, timeout behavior, and authenticated ownership must be exercised in M2/M3 before being described as supported lab behavior. Reuse the SDK lifecycle rather than creating a competing state machine.

## Current profile and limits

The only supported profile is `local-demo`, with binding restricted to `127.0.0.1` or `::1`. It uses synthetic text, no tools or model, and no authentication. Streaming, push notifications, extended cards, and 0.3 compatibility are disabled. Text length is validated; broader HTTP payload/concurrency controls and the authenticated security profile remain future work.

This macOS workspace marks generated environment files hidden, which can make Python skip editable `.pth` files. Clearing the flag temporarily worked, but the workspace reapplied it. The installed lab therefore uses a regular wheel. The README documents `--no-editable` commands and refreshing that wheel after source edits; no source-path override masks installation failures. Standard editable development remains available in environments without this behavior.

## Next milestone

M2 builds the knowledge and coordinator workflows, two independent local processes, discovery/delegation through the same tested SDK boundary, and a supervised demo. Django/MCP and supply chain code remain outside the core milestone.
