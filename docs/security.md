# Security boundaries and evidence

Reviewed: 11 October 2026. Baseline: Python 3.12.13, `a2a-sdk` 1.2.2,
A2A 1.0 JSON-RPC. This document travels with a standalone clone. The workspace
security study and presentation materials are authoring artifacts outside this repo.

The lab demonstrates application enforcement around deterministic agents. It does
not establish production readiness or evaluate a model's prompt-injection resistance.
The [constitution](constitution.md) owns engineering rules; this document maps
current behavior to evidence. Run the [workshop](guides/workshop.md) to inspect it.

## Trust and authority

The operator selects a synthetic Alice or Bob credential. Authentication verifies
actor, represented user, role, recipient, and expiry. Task access is scoped by
actor and represented user. The coordinator uses its own recipient-specific service
credential for that represented user; it does not forward the upstream bearer.

Discovery starts with an exact configured loopback destination, then fetches a
live card. The client validates protocol, binding, expected capability, endpoint,
content modes, and authentication declaration. A card cannot authorize another
destination. The opt-in discovery topology adds authenticated curated search;
independent policy validates every returned ID, capability and URL before card
fetches. There is no automatic registration, signed card or TLS server identity.
A compromised peer at the allowed endpoint remains
a threat. Production transport encryption is required by the
[A2A 1.0 specification](https://a2a-protocol.org/v1.0.0/specification/#134-general-security-best-practices).

Messages, cards, references, and artifacts remain data. They cannot select a
different workflow, credential, network destination, or approval role. Domain
validation checks shape and bounds; it does not establish factual accuracy or
semantic provenance. There is no LLM, arbitrary tool execution, persistent
conversation memory, or external artifact download in the current workflows.

## Control evidence

These are our mappings to the themes in
[OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html),
not an OWASP certification. Paths below identify the actual enforcement and tests.

| Concern | Enforcement | Evidence | Practical limit |
| --- | --- | --- | --- |
| Least privilege | `security/http.py`, `security/identity.py`: default-denied role/method/route access and recipient-bound principals | `tests/security/test_action_api.py`; `test_authentication_rejects_credentials_before_execution` in `tests/security/test_identity_lifecycle.py` | Operator controls all teaching accounts; no external issuer or online revocation. |
| Untrusted input | `config.py`, `a2a/cards.py`, `a2a/client.py`, `domain/models.py`: trusted configuration, contract checks, bounded typed results | `tests/contract/test_local_agents.py`, `tests/contract/test_extension.py` | Injection-like data cannot grant authority; no model robustness measurement. |
| Context isolation | `a2a/identity.py`, `a2a/store.py`: verified identity and owner-scoped SDK tasks | `test_reads_artifacts_lists_and_cancellation_are_owner_scoped`; `test_untrusted_owner_metadata_cannot_change_identity` | In-memory task isolation; no persistent retrieval/memory system assessed. |
| Human action integrity | `security/approval.py`, `a2a/actions.py`: exact proposal, separate approver, expiry, snapshot check, atomic consumption and idempotent receipt | `tests/security/test_approval_integrity.py`, `tests/security/test_action_api.py` | Only a synthetic local-display receipt; not physical human authentication or durable business recovery. |
| Output validation | `domain/models.py`, `a2a/client.py`, `web/app.js`: one bounded answer artifact, bounded references and Markdown with raw HTML/images disabled and safe link schemes | `tests/contract/test_local_agents.py`, `tests/unit/test_review.py`; browser walkthrough | Shape validation cannot prove correctness; no file execution. |
| Monitoring | `security/http.py`, `a2a/client.py`: generated correlation and safe actor/operation/decision traces | `tests/security/test_private_credentials.py`, `tests/integration/test_secure_delegation.py` | No tamper-evident log, SIEM integration, alert SLA, or operator attribution beyond teaching identities. |
| Peer delegation | `a2a/limits.py`, `a2a/client.py`: exact URL policy, no redirects/proxies/send retries, explicit service authority | `tests/contract/test_limits.py`; `test_delegation_uses_service_authority_instead_of_forwarding_user_token` | Literal loopback only; registry federation, DNS rebinding and remote authentication need a new design. |
| Privacy | `security/identity.py`, `container_credentials.py`: private files, recipient separation, redacted values | `tests/security/test_private_credentials.py`, `tests/security/test_container_credentials.py` | Local operator/Docker administrator can obtain credentials; no confidential-computing claim. |
| Adversarial verification | Contract, security, and live HTTP tests exercise denial and race behavior | `tests/security`, `tests/contract`, `tests/integration` | Deterministic fixtures and automated approver requests, not a penetration test or real human review. |
| Directory poisoning/disclosure | `a2a/directory.py`, `security/policy.py`: bounded topic-only queries, independent exact candidate policy, owner-filtered results and peer-enforced ACL | `tests/security/test_directory.py`, `tests/integration/test_discovery.py` | General cards are public; approved loopback identities only, no publication/cache/federation service. |
| Browser/session boundary | `web/server.py`: exact Host/Origin, JSON/CSRF, private cookies, bounded synthetic sessions, session-owned task APIs; `a2a/traces.py` checks SDK owner scope | `tests/security/test_web_boundary.py`, `tests/integration/test_web.py`, `scripts/browser-smoke.py` | Operator identity simulation, no production login; HTTP only on host loopback, ephemeral sessions/history. |
| Review amplification/incomplete results | `a2a/directory.py`: at most three distinct parallel sends, shared deadline, per-peer budget, attributed outcomes, rejected oversized findings, no recursive expansion or retries | `tests/integration/test_web.py`, `tests/unit/test_review.py` | Lost replies can leave unknown outcomes; no fairness or durable recovery. |

## Availability, lifecycle, and approval details

Defaults cap input at 1,000 characters, payloads at 65,536 bytes, active requests
and workflows at four each per agent, task polls at 100, and retained tasks at 128.
Each approval collection is capped at 128. The default workflow deadline is five
seconds; a client exchange has a ten-second total budget, plus at most one second
for cancellation cleanup. HTTP and workflow limits are separate, not one shared
four-operation quota. [Configuration](../README.md#configuration) is authoritative.

Known delegated tasks receive best-effort cancellation. Serialized task publication
prevents late artifacts after cancellation, including a provider that suppresses
cooperative cancellation in the test. Lost start or cancel responses can leave a
remote outcome unknown. Timeout is not proof of cancellation or business rollback.
Tests: `test_cancellation_blocks_late_results_even_if_provider_suppresses_cancel`,
`test_polling_budget_cancels_pending_work_and_does_not_retry_send`, and the live
HTTP cases in `tests/integration/test_secure_delegation.py`.

Approval binds the owner scope, task, artifact, operation, destination, label,
revision, content snapshot, and expiry. Execution rechecks them and records one
receipt under an in-memory lock. An identical retry with the same actor and key
returns the confirmed receipt, including after the grant expires, while the
request's credential must still be valid. A changed retry or new-key replay fails.
Several grants for one proposal still cannot release it twice. This is an example
of applying [OWASP transaction authorization](https://cheatsheetseries.owasp.org/cheatsheets/Transaction_Authorization_Cheat_Sheet.html)
to an application executor. Restart loses all tasks, proposals, grants, and receipts.

Finite caps limit work but do not provide fairness, rate limits, per-user quotas,
expiry cleanup, GPU budgets, or a durable ledger. A caller can exhaust global
retention and deny new work to other callers. These are deployment gaps.

## Deployment and optional integrations

Docker uses non-root containers, read-only roots, dropped capabilities, finite
CPU/memory/PID limits, separate credential mounts, an internal network, and no
host-published agent ports. The opt-in browser publishes only its gateway on host
loopback. Agents share the network namespace; this is not network
isolation between them. Native processes share the operator's OS account. Neither
path provides TLS, signed peer identity, a protected approval UI, durable state,
central identity/revocation, dependency vulnerability assurance, or incident response.

Browser ingress is a separate credential-free relay on the browser bridge and
internal lab network. It publishes `127.0.0.1:8080` and forwards only the fixed
gateway's browser routes, preserving Host/Origin/CSRF/cookies and rejecting
redirects and excess bytes. It mounts no credentials. Only ingress has an external
bridge; agents/gateway retain the internal network. Application destination policy
is not OS containment of a compromised relay. Tests in `test_browser_relay.py`
cover fixed destinations, duplicate-header preservation, routes, bytes and redirects.

Before remote deployment, review issuer/audience and delegation, TLS and server
verification, card publication/cache expiry/revocation, every exposed operation,
tenant quotas, persistent idempotency and transaction boundaries, audit retention,
secret rotation, monitoring, dependency scanning, and recovery. If adding streams,
callbacks, files, or registries, assess each new subscription, URL, content type,
and resource owner explicitly. A signed card still needs a trusted signer and
does not grant permission.

A [local model integration](guides/local-model-integration.md) is optional and not
implemented. Keep inference behind the existing domain port. Define context
provenance, output validation, token/time/memory budgets, cancellation and local
endpoint policy before connecting it. Model prose cannot issue grants or tokens.

The optional supply chain uses A2A between sourcing/vendor agents and MCP to
access Django business tools. Django must independently check tenant, stock,
price floors, exact human approvals and transactional reservations. MCP tool
annotations are descriptions rather than permissions; follow its
[tools contract](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)
and [security guidance](https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices).
No Django/MCP service or commercial action exists in this lab.
