# Lab 1: Discover a peer and delegate over A2A

Learn how a configured peer address becomes a validated Agent Card and an
actual HTTP call. The deterministic agents use packaged synthetic notes,
so no model account is needed. Follow the repository [setup](../../README.md)
first. Use its non-editable fallback on affected macOS workspaces.

## Run and follow the exchange

```sh
uv run a2a-lab demo --text "What belongs in a runbook?"
```

Find these events in the output:

1. `supervisor.started` and `supervisor.ready` identify two child processes.
2. The client fetches the coordinator card and checks its skill and interface.
3. The coordinator fetches the knowledge card and sends a real HTTP request.
4. The knowledge agent completes its task with a JSON answer artifact.
5. The coordinator completes a distinct task with its composed answer.
6. `supervisor.stopped` appears for both children before the final JSON report.

The final report includes an answer and the fixture reference `runbook`.
Task identifiers are generated for each exchange; they are not access tokens.
The stores are separate and ephemeral. No streamed progress is advertised.

Try questions about Agent Cards and secure delegation, then an unrelated
question. The knowledge agent matches keywords; it reports when no bundled
note matches rather than inventing a source. This lab demonstrates protocol
collaboration and application policy, not an LLM's reasoning quality.

## Inspect the card and individual agents

In separate terminals, start the knowledge and coordinator agents:

```sh
uv run a2a-lab serve knowledge
uv run a2a-lab serve coordinator
```

In a third terminal:

```sh
curl http://127.0.0.1:8102/.well-known/agent-card.json
uv run a2a-lab call --agent knowledge --text "What should Agent Cards describe?"
uv run a2a-lab call --agent coordinator --text "How do we design secure delegation?"
```

Inspect `supportedInterfaces`, `skills`, content modes, and capabilities.
The knowledge skill is `engineering-knowledge`; the coordinator skill is
`engineering-coordination`. Inputs are text; outputs are JSON answer data.
Application version and A2A protocol version are different concepts.
Stop manually served processes with Ctrl+C when finished.

## Observe controlled failures

Leave the coordinator running, stop the knowledge agent, and call the
coordinator again. The lookup fails safely and the CLI returns a nonzero exit
status. It does not choose an arbitrary replacement peer or retry endlessly.

With a manually served agent still occupying a demo port, run `demo`.
The supervisor rejects the port collision and does not attach to that server
or stop it. Stop your manual agents, then run `demo` successfully again.

Inspect the runnable rejection and boundary tests:

```sh
uv run pytest tests/contract/test_local_agents.py tests/contract/test_limits.py
uv run pytest tests/integration/test_demo.py
```

These cover missing skills, changed interfaces, malformed cards, redirects,
stalled discovery, oversized bodies, execution capacity, and process cleanup.

## Discuss security and discovery

The peer address comes from approved deployment settings. A card supplies
capability metadata; application checks decide whether its endpoint and
capability are suitable. Neither discovery nor a skill description supplies
identity, tool authority, or approval. Peer data cannot add destinations or
cause a second delegation.

Relate the controls to the constitution's OWASP principles: untrusted input,
least privilege, bounded work, and verifiable execution. Explain what is still
missing: authenticated identity, resource ownership, human approval, durable
state, retention limits, and a demonstrated cancellation contract.

Review the M2 decision (private decision record). Before
using a directory, decide who may publish entries, which callers may discover
them, and how identity, freshness, and revocation will be checked. A searchable
registry remains an optional extension; the current lab uses direct
configuration and live well-known card retrieval.
