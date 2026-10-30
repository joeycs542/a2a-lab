# Lab 7: Interactive discovery and bounded specialist review

Use a browser to ask the coordinator, watch discovery, and receive attributed
findings from up to three independently running A2A agents. Deterministic topic
matching and bundled notes keep the lab reproducible without downloaded models.
Each run creates a new task; the page displays the latest run, not agent memory.

The collaboration map follows Client → Coordinator → Specialist → Coordinator
→ Client. Start with the one-specialist question, then compare Alice and Bob on
three-specialist review. The execution stages show capability/card validation,
selection, query, acknowledgment, response and delivery. A send alone is not
receipt evidence; a returned child task ID is. Processing describes the configured
keyword-match/bundled-note workflow, not model thoughts. No model is downloaded.

After execution ends, use **Replay**, **Pause/Resume**, **Previous step**, and **Next step**. Replay starts
paused; use Resume for automatic playback. Previous/Next pause playback while
stepping through the evidence. Replay
presents the recorded event order at a teaching pace; it does not reproduce wall
clock timing, send requests or run agents again. Later evidence and the answer
remain hidden until their recorded step. The final coordinator response appears above the map at delivery. Bottom
**Specialist work** disclosures show each observed agent’s processing summary,
task receipt and individual returned finding. Individual findings are extracted
only from the coordinator’s fixed role sections and appear after that peer’s
response event; unavailable or unexpected-format findings remain explicit.
**Inspect execution evidence** retains the raw events and task IDs.
Refresh recovers the latest session task and its replay from server-retained
traces. There is no durable recording; restart or session expiry loses recovery.
Identity changes clear the display and lock submission until token rotation ends.
The gateway retains questions within the existing bounded session, not in traces.

## Start and interact

Run from the code repository with Docker Desktop running:

```sh
docker compose -p a2a-desk -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml up --build -d --wait
```

Open [the engineering desk](http://127.0.0.1:8080). Use that exact address; the
gateway validates Host and Origin. Only this gateway is published, on host
loopback through a separate credential-free ingress relay. Agents and gateway
retain their internal network; the relay forwards only fixed browser routes and
mounts no credentials. Directory and A2A ports remain private. Every service uses the same
locked runtime image; there are no host source/environment/credential mounts.
Start with a fresh project rather than reusing baseline credential volumes.

1. As Alice, click a supported-topic prompt and ask the coordinator. The decision
   panel shows the directory query, live card checks, selection, child task and
   final outcome. A compatible card is metadata, not proof of execution success.
2. Ask `Review runbook, security and release readiness.` Expect three attributed
   sections and their actual fixture citations. Only those three roles may be
   contacted; no recursive discovery or automatic send retry occurs.
3. Select Bob and ask the same question. Expect an **incomplete review** with
   runbook/release findings. Security is Alice-only: catalog filtering and the
   security peer's invocation policy independently enforce that restriction.
4. Ask an unsupported topic. Expect an explicit no-match response and no catalog
   or specialist request. Single mode in [Lab 6](../06-agent-discovery/README.md)
   asks for clarification on equally ranked topics; review mode consults all
   matching permitted specialists instead.
5. Ask `[slow] release` and promptly click **Cancel current task**. The result is
   canceled without an answer artifact. Known child IDs receive best-effort
   cancellation; a lost start/cancel response can still leave an unknown outcome.
6. Ask `[fail] runbook release`. Expect explicit failed findings and an incomplete
   review. No validated citation is invented for a failed peer.

The default fixture delay is two seconds. For review timeout behavior, a separate
override can set `A2A_LAB_FIXTURE_DELAY_SECONDS` to four on specialists; per-peer
review time is 2.5 seconds, inside the default five-second overall workflow.
Do not add the baseline workshop's eight-second delay expecting successful reviews.

## Availability and CLI alternatives

Stop runbook, then ask `runbook release` in the browser:

```sh
docker compose -p a2a-desk -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml stop runbook
```

Expect an excluded candidate in the panel, a validated release finding, and an
incomplete review. Restore the specialist afterward:

```sh
docker compose -p a2a-desk -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml start runbook
```

For CLI review with no host-published port, use a fresh named project and
`compose.review.yaml` instead of `compose.web.yaml`:

```sh
docker compose -p a2a-review -f compose.yaml -f compose.discovery.yaml -f compose.review.yaml up --build -d --wait
docker compose -p a2a-review -f compose.yaml -f compose.discovery.yaml -f compose.review.yaml run --rm client call --text "runbook security release"
docker compose -p a2a-review -f compose.yaml -f compose.discovery.yaml -f compose.review.yaml --profile tools down --volumes
```

Native use requires six separately served roles and fresh discovery credentials
as described in Lab 6. Set `A2A_LAB_DISCOVERY_MODE=review` consistently on coordinator
and clients, then `uv run a2a-lab serve-web` in another terminal. The gateway uses
the private operator directory and defaults to loopback port 8080. If changing
that port, change `A2A_LAB_WEB_PORT` and `A2A_LAB_WEB_ORIGIN` together. Native service
processes share the operator's OS account.

## Security and bounded behavior

Alice/Bob are labeled **synthetic operator identities**, not production login.
The operator can simulate both. Browser scripts receive a session cookie and CSRF
nonce; bearer credentials remain server-side. Cookies are HttpOnly/SameSite Strict
for local HTTP. Host, exact Origin, JSON content type and CSRF are checked, including
duplicate security headers. Sessions expire after 30 minutes and are capped at 32;
each session retains at most 16 turns. Switching identity requires terminal tasks,
clears that session's task list and rotates its CSRF nonce.

Session ownership gates task inspection/cancel. The trace application API separately
checks SDK actor/owner scope. Traces omit prompts and credentials, retain at most
64 distinct events of 300 characters per task, and share the finite task cap.
Responses render Markdown through a pinned local markdown-it bundle, with raw
HTML and images disabled and links restricted to HTTP, HTTPS or mailto. Questions,
processing summaries and raw events remain text-only. The content policy stays self-only.
Refresh recovers known session task IDs; server restart loses tasks, sessions and
traces. The browser polls finitely and does not advertise A2A streaming.

Review allows at most three distinct sends. Each finding must fit 2,000 characters
and one reference; excessive output is rejected without truncating it. Combined
results preserve the existing 8,192-character/four-reference `Answer` contract.
Missing, failed, invalid or unknown findings make the review incomplete. Timeout
does not imply rollback. These informational agents do not approve releases,
procure supplies, inspect systems or execute tools. Read the
[security evidence](../../docs/security.md) for enforcement and deployment gaps.

## Verification and teardown

```sh
docker build --target verify -t a2a-lab:verify .
docker compose -p a2a-desk -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml run -T --rm --entrypoint python client - < scripts/browser-smoke.py
```

The HTTP smoke checks review, permission-limited partial results, independent
sessions, CSRF/origin and cancellation through the installed gateway. The full
suite also tests forged candidates/cards, all-child cancellation, unknown timeout,
oversized findings and direct unauthorized trace reads. These are policy checks;
they do not evaluate model prompt resistance.

Stop the desk while preserving teaching credentials with:

```sh
docker compose -p a2a-desk -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml down
```

To deliberately remove **this project's** expiring credentials and operator files,
add `--profile tools` before `down` and `--volumes` afterward. Seven credential
volumes plus operator-work are removed; do not reset another project. Credentials
expire after one hour. Use fresh project state before another session.
