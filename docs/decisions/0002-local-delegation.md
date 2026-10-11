# M2 local discovery and delegation

Date: 11 October 2026  
Status: Implemented and verified

Keep the M1 Python 3.12.13, official `a2a-sdk` 1.2.2, and A2A `1.0`
JSON-RPC baseline. Add deterministic coordinator and knowledge workflows,
each served by an independent process with its own SDK task store.

## Contracts and boundaries

Application workflows exchange the typed `Answer` model through the narrow
`KnowledgeLookup` port. SDK wire types remain in `a2a_lab.a2a`. The knowledge
workflow matches bounded text against three packaged synthetic notes. The
coordinator makes exactly one knowledge lookup and composes the validated
answer without executing instructions in it.

Cards are typed factories built from validated settings. Required skill IDs
are `engineering-coordination` and `engineering-knowledge`. Inputs are
`text/plain`; outputs are `application/json`. The executor uses SDK tasks,
`TaskUpdater`, and one JSON data artifact named `engineering-answer`, with
`answer` and `references`. It does not maintain a second task state machine.

The client fetches a live card, validates metadata, skill, content modes,
protocol/binding, and the exact configured interface, then sends one SDK
request. It accepts one completed task and validates the artifact as bounded
application data. Extra result fields cannot add actions or destinations.

Use direct configuration and the well-known card path for initial discovery,
as described in the [A2A discovery guidance](https://a2a-protocol.org/v1.0.0/topics/agent-discovery/).
A separate registry would add deployment and governance responsibilities
without improving the two-agent learning objective. Searchable directories,
registration, and multiple-peer ranking remain optional extensions.

## Execution controls and process ownership

- Bind to configured literal loopback addresses. Both agent ports must differ.
- Permit only exact configured card and RPC URLs, before network access.
  Disable inherited proxy settings, redirects, retries, and compression.
- Bound inbound body reads, decoded peer payloads, input length, and workflow
  execution. Apply a whole-exchange client deadline in addition to HTTP timeouts.
- Bound active HTTP requests and active SDK workflows separately. A caller
  using `returnImmediately` cannot bypass the execution capacity check.
- Keep traces to event names, approved targets, bounded escaped task IDs,
  and process IDs. Do not log questions, card bodies, or credentials.
- Reserve both listening sockets before launching children. Inherit the
  matching socket into each POSIX child and validate its stream type and
  configured loopback address before serving. Release the parent's copy.
  This prevents readiness from attaching to an unrelated existing server.
- Give children validated settings and a temporary working directory.
  Readiness checks use served cards. After success, failure, or interruption,
  terminate and reap owned children; force-kill after the graceful deadline.

The default byte limit is 65536, input length 1000 characters, active request
and workflow limits 4 per process, workflow timeout 5 seconds, client exchange
deadline 10 seconds, readiness deadline 15 seconds, and graceful shutdown
wait 3 seconds. Character and byte budgets are independent.

Add `types-protobuf` only as a development dependency for strict checking of
the SDK's protobuf JSON conversion boundary. The lock selects
`7.35.1.20260906`; runtime SDK/framework versions are unchanged.

## Verification evidence

- All 72 unit, contract, and integration tests passed on macOS ARM64.
- Ruff lint and format checks and strict mypy checks passed.
- A locked regular-wheel environment in a temporary directory ran the demo
  from outside the repository. The installed package supplied all notes.
- The CLI trace demonstrated coordinator and knowledge PIDs, live card fetches,
  an outbound knowledge RPC, distinct completed SDK tasks, a runbook reference,
  and cleanup of both children.
- Rejection checks cover malformed/incompatible cards, missing capabilities,
  changed endpoints, redirects, malformed peer data, oversized bodies,
  stalled discovery, workflow deadlines, and execution capacity.
- Real-process checks cover success, occupied ports, second-child startup
  failure, readiness timeout, an unavailable knowledge peer, and Ctrl+C.
  They verify that owned PIDs disappear and ports can be rebound.
- Inherited-listener tests reject a public binding and a different port.

The workspace environment had stalled reads of existing dependency files.
Verification used a fresh temporary environment, and the workspace environment
was refreshed from the same lock. The existing non-editable installation
fallback remains documented; no source-path override is used.

## Limits and next milestone

The profile is synthetic, unauthenticated loopback HTTP. Destination checks
do not authenticate another local process. SDK task stores are ephemeral and
have no retained-task budget in M2. SDK task routes exist, but authenticated
ownership, retrieval/cancellation exercises, delegated cancellation, and
approval integrity remain M3 work. A local timeout does not prove remote
cancellation. No streaming, push notifications, signed/extended cards, model
provider, MCP backend, or business commitment is advertised as implemented.

The first exercise and setup instructions live in the repository so a
standalone clone can run the lab. Future security claims must link to actual
enforcement and verification under the project constitution.
