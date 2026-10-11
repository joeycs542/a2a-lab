# 0009 Curated discovery and interactive engineering desk

Date: 11 October 2026. Status: Accepted; implemented and locally verified.

## Decision and behavior

Preserve the default two-agent baseline. Add an opt-in authenticated discovery
topology with three independent A2A specialists, a read-only directory, a browser
gateway and bounded review. No new dependency, inference runtime or model is used.

Directory queries contain typed supported topics, never raw questions or upstream
bearers. Independently bind returned IDs, capabilities, card/RPC URLs and owner
permission to trusted startup configuration before live-card fetches. Then check
A2A 1.0 JSON-RPC, capability, modes and auth profile. Neither a card nor catalog
membership grants authority. The directory/search/trace APIs are application APIs,
not additional standardized A2A methods.

Each service has a recipient-bound verifier mount. The coordinator alone holds
outbound service credentials for each represented user; it does not forward user
tokens. Only the initializer mounts the complete writable issuer set. Switching
existing credentials' topology fails without overwriting them. General cards are
public. Alice can invoke all specialists; Bob can invoke runbook/release. Security
independently enforces Alice-only invocation even with a valid recipient token.

Single mode ranks viable peers by distinct supported keywords. No match, no
authorized viable candidate and tied topics have explicit informational answers;
there is one selected send. Review mode consults at most three matching permitted
specialists in parallel. Cards advertise the selected mode and clients validate
that trusted expected skill. No recursive expansion or send retry occurs.

The default overall workflow is five seconds; each review peer has 2.5 seconds,
plus bounded best-effort cleanup. Known started children are owned/canceled, and
late artifacts cannot complete a canceled root. Lost replies can leave unknown
outcomes. Attribute each accepted finding; missing, failed, invalid or unknown
findings make the review incomplete. Reject findings over 2,000 characters or one
citation without truncation. Three findings fit the original Answer contract of
8,192 characters/four references.

## Browser and network boundary

The gateway retains bearers server-side. Labeled synthetic Alice/Bob sessions use
HttpOnly/SameSite Strict cookies, exact Host/Origin, JSON/CSRF and duplicate-header
checks. Sessions expire after 30 minutes, cap at 32, and retain 16 turns each.
Identity changes require terminal tasks, clear session task ownership and rotate
CSRF. Task APIs deny identifiers from another session; trace reads independently
check SDK actor/owner scope. Traces omit prompts/credentials and cap at 64 distinct
300-character events per retained task. State is ephemeral. Text-only rendering
and a self-only content policy keep findings inert. Refresh recovers known tasks;
finite browser polling does not advertise A2A streaming.

Docker Desktop 29.5.2 suppressed direct publication from the internal namespace:
HostConfig listed the port, NetworkSettings had no host mapping, and host access
failed while internal HTTP checks passed. Use a separate credential-free relay
on browser/internal networks, publishing only 127.0.0.1:8080. Forward fixed gateway
browser routes, preserve security headers/cookies and reject redirects/excess
bytes. Agents/gateway remain internal; A2A/directory ports stay private. Ingress
mounts no credentials. Its application policy is not containment of a compromised
process. This is an observed setup result, not a universal Docker-version claim.
[Docker port publication](https://docs.docker.com/engine/network/port-publishing/)
and [Compose networking](https://docs.docker.com/compose/how-tos/networking/) are the
network references.

## Verification and consequences

Locally verified on the uncommitted working tree based on 3ed65f0, Linux arm64,
Python 3.12.13, SDK 1.2.2 and unchanged uv lock:

- Locked lint/format, strict mypy (40 source files), and **157 tests** passed with
  external networking disabled during checks.
- Real Compose CLI checked live catalog/cards, all single routes, Bob filtering
  and direct denial, no-match and ambiguity. Installed supervised baseline,
  discovery and review demos passed without external networking.
- Installed ingress/gateway HTTP smoke passed review, permission-limited partial
  findings, session isolation, CSRF/origin and cancellation.
- Tests cover direct unauthorized trace reads, every started child's cancellation,
  unknown timeout, failed partial findings and oversized output rejection.
- Browser interaction checked Alice's three findings, Bob's incomplete two-peer
  answer, cancellation, literal markup and refresh. Desktop/mobile views were
  inspected; the mobile check showed no horizontal overflow.
- Compose modes and updated CI were locally validated, including actionlint.
  Hosted GitHub CI awaits a committed/pushed change.

The user changed Docker disks after the storage interruption. Temporary test state
is cleaned separately from other Docker projects; rebuilt lab images remain for
the startup commands. This is a local operator simulation with ephemeral state,
not production login/server identity or a durable workflow. The synthetic action
approval boundary remains separate; browser reviews cannot deploy or procure.
Models, dynamic publication and transactional business tools remain later work.

See [A2A discovery](https://a2a-protocol.org/v1.0.0/specification/#82-discovery-mechanisms),
the [constitution](../constitution.md), [security evidence](../security.md),
[Lab 6](../../labs/06-agent-discovery/README.md) and
[Lab 7](../../labs/07-interactive-review/README.md).
