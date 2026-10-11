# M3 Authenticated lifecycle and action integrity

Date: 11 October 2026  
Status: Implemented with verification recorded below

Retain Python 3.12.13, official `a2a-sdk` 1.2.2, and A2A `1.0` JSON-RPC.
Reuse SDK ownership, task storage, events, retrieval, listing, and cancellation.
Keep the original `local-demo` and add `local-secure` as a caller-authenticated
loopback teaching profile. Both agents still use fixtures; no model is installed.

## Identity and permissions

The teaching issuer generates random opaque tokens with recipient, actor,
represented owner, role, and expiry bound in private server verifier records.
Token values are stored only in the relevant private client/outbound files;
inbound authentication uses SHA-256 digests and constant-time comparison.
Files are created in a fresh directory with mode 0600 and never overwritten.
New HTTP operations reject missing, invalid, expired, duplicate, or
wrong-recipient credentials before parsing request bodies.

| Credential role | Permitted operations | Authority boundary |
| --- | --- | --- |
| Alice or Bob user | A2A calls; owned coordinator proposals and releases. | SDK scope is actor plus represented owner. |
| Coordinator service for Alice or Bob | Knowledge-agent A2A calls. | Separate knowledge-recipient token; never the upstream caller's token. |
| Human Alice or Bob | Coordinator `/control/approve`. | Can approve only that user's exact displayed proposal. Cannot call A2A. |
| Public caller | GET public Agent Card. | Descriptive metadata only; no private tasks, content, or credentials. |

Other protected paths and HTTP methods are denied by default. Existing A2A
resource operations use the SDK's owner-scoped store; caller-supplied ownership
metadata cannot change the scope. Actor and owner are both included so direct
user tasks and service-delegated tasks are distinct. Card signing and an
external identity provider remain deployment considerations.

The coordinator loads only its server verifier file and outbound service
credentials. The knowledge agent has no outbound credentials. A trusted
request context selects the represented user's configured delegation token.
Neither question text nor peer output chooses the identity or destination.
Generated `ROLE_USER` message tags describe protocol conversation direction;
they do not give a service human approval authority.

## Lifecycle and bounded work

`[slow]` supplies cooperative delayed fixture work; `[fail]` supplies a controlled
failure. A workflow owns its child task, checks cancellation before publishing,
and serializes cancellation against status/artifact publication. The SDK's
`TaskUpdater` emits terminal states; application guards prevent late writes
without implementing a competing protocol state machine.

Authenticated delegation starts one SDK task, retains its returned ID, and
polls within the deadline and finite read budget. Interruption or budget
exhaustion attempts cancellation of that known task using the original scoped
service credential. Cleanup is bounded to one additional second. A completed
last allowed poll is accepted; an unfinished final poll cancels pending work.
There are no send retries or recursive peer delegation.

Default limits are five-second workflows, ten-second client exchanges,
100 polls, four active requests/workflows per process, 65536-byte payloads,
128 retained SDK tasks per server, and 128 records in each approval collection.
Record limits reject new entries without evicting replay evidence. Stores
remain in memory; there is no automatic retention expiry or durable recovery.

Cancellation is cooperative. Supplied fixtures and HTTP lookups support it;
arbitrary blocking or cancellation-resistant model code needs an appropriate
adapter/process design. If a start response is lost before the ID is known,
or cancellation cannot be acknowledged, the client preserves uncertainty.
The local workflow deadline still bounds the supplied remote fixture work.
The process supervisor remains responsible for reaping owned children.

## Exact human approval

The coordinator exposes a synthetic control API outside its Agent Card skills:
`/actions/proposals`, `/control/approve`, and `/actions/execute`. A proposal
can reference only an owned completed answer artifact. It stores validated
terms and a fingerprint of the artifact's current content. The terms fix the
operation to `release-fixture` and destination to `local-display`, with a task,
artifact, revision, and label. The revision is a reviewed local proposal term;
the content fingerprint protects the actual artifact snapshot.

The human-control role approves the exact stored digest and reviewed terms
for its user's scope, with an expiry from 1 through 300 seconds. An agent's
approval flag, a role claim, an unknown approval ID, or an altered revision
cannot create authority. Execution reads the current owned artifact and
checks actor, operation, resource, terms, revision, snapshot, expiry, and
consumption state. Task continuation is disabled; completed artifacts cannot
be changed through the public lab API.

One application lock consumes the grant and records one synthetic release
receipt atomically. A proposal cannot be released twice even if two grants
exist. The same actor/idempotency key with identical terms returns its saved
receipt, including after grant expiry; a changed retry or new-key replay is
denied. This is a confirmed local JSON display result, with no payment,
procurement, file publication, or external message. Durable transactions and
commercial invariants belong to the optional Django/MCP sample.

## Audit and verification

Authentication derives correlation IDs on the server. Workflow and policy
events carry identities, known destinations, bounded escaped task IDs, and
correlation fields without questions, bearer values, or full card bodies.
The SDK context keeps only the validated `a2a-version` header, verified
principal, and correlation ID. Inspection showed the SDK's own version guard
needs that header; removing all headers would incorrectly fall back to 0.3.

Verification covers all earlier milestones plus authenticated task access,
invalid/expired/wrong-recipient tokens, direct/service scope separation,
default-denied routes, controlled failure, timeout, cooperative shutdown,
late-result prevention, and polling/retention budgets. Approval cases include
missing, altered, expired, wrong-actor, concurrent, and replayed authority.
Real-process tests verify authenticated HTTP delegation, downstream
cancellation, a simulated human-role release, and child-process cleanup.
Ruff lint/format and strict mypy are required alongside behavioral checks.

All 108 behavioral tests, Ruff lint/format checks, and strict mypy passed.
A regular-wheel installation also passed the workspace's `demo --secure`
and an actual CLI walkthrough of owned lookup, Bob denial, simulated
human-role approval, identical-key retry, replay denial, cancellation, and
child cleanup. Stalled reads of existing workspace dependencies required a
full refresh from the unchanged lock; the clean temporary installation passed
throughout. Private local teaching credentials were generated under the
ignored runtime directory without printing their values.

These are deterministic application policy tests. They do not evaluate a
model's prompt resistance or prove that a physical human reviewed an artifact.
The test suite simulates the human-control role to check enforcement.

## Deployment limits and next milestone

Tokens are issued by the local operator, and that operator holds all teaching
identities. Processes share an OS account; separate files are logical privilege
separation, not a sandbox. This profile uses loopback HTTP, with no TLS,
cryptographic server identity, signed cards, online issuer, revocation service,
persistent ledger, or restart recovery. Rotation uses a new private directory
and server restart. SDK streaming, push, and extended cards remain disabled.

Use the [A2A specification](https://a2a-protocol.org/v1.0.0/specification/),
[OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html),
and [transaction authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
for the M5 deployment study. M4 next packages the working boilerplate into
implementation and Agent Card coding skills, with an extension exercise and
local model adapter guidance. No Django/MCP or model integration is started.
