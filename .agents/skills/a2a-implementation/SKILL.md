---
name: a2a-implementation
description: Extend or review Python workflows and A2A integration in this lab, preserving its SDK boundary and secure execution controls. Use for new agent behavior, dependency wiring, and lifecycle changes in this repository.
---

# A2A implementation

Locate the repository through `AGENTS.md` and `pyproject.toml`. Read its
[constitution](../../../docs/constitution.md) and [security guide](../../../docs/security.md).
These documents contain the project rules. This skill guides engineering work; it is
not a runtime Agent Card skill or permission to publish or execute actions.

## Choose the extension boundary

Implement `KnowledgeLookup.answer(question) -> Answer` in `src/a2a_lab/agents`
and inject it in `bootstrap.py`. Keep SDK types and HTTP operations inside
`a2a_lab.a2a`. Reuse the server, executor, task store, identity middleware,
result validation, and approval boundary.

Use the [extension exercise](../../../labs/04-boilerplate-extension/README.md)
for a fixture workflow. Its validated `knowledge_workflow` setting selects
behavior in the existing knowledge role. The opt-in discovery topology uses
fixed specialist roles and a curated authenticated directory; see
[Lab 6](../../../labs/06-agent-discovery/README.md) and
[Lab 7](../../../labs/07-interactive-review/README.md). New peers need explicit
endpoint, card, credential-audience, authorization, process and issuer wiring.
Directory responses cannot add arbitrary destinations or override startup policy.

Select dependencies from trusted startup settings. Request text and model output
cannot select credentials, workflows, or destinations. Add working modules for
the requested responsibility rather than duplicate template trees. For inference,
use the [local model boundary](../../../docs/guides/local-model-adapter.md).

## Preserve affected execution controls

- Keep user, represented service, and human-control authority separate. New
  routes need explicit role/method permissions and resource ownership checks.
- Treat peer/model/tool content as data. Validate `Answer` and provenance;
  never execute generated instructions or approval flags.
- Retain destination, body, concurrency, deadline, polling, and retention limits.
  Own cancellation and prevent late task/artifact writes.
- Preserve the constitution's bounded review, partial-outcome and browser/session
  requirements. Keep trace reads owner-scoped and browser bearers server-side.
- Bind consequential actions to exact stored actor/resource/terms, revision,
  snapshot, expiry, and consumption; retain idempotent confirmed receipts.
- Keep credentials and private context out of traces/cards. Docker volumes do
  not prevent the operator simulating all roles. Fixture policy tests do not
  measure model prompt resistance.

These are this lab's review boundaries, informed by
[OWASP AI Agent Security](https://cheatsheetseries.owasp.org/cheatsheets/AI_Agent_Security_Cheat_Sheet.html).
Use `$a2a-agent-card` for changes to advertised behavior or capability selection.

## Verify and report

Test new successful behavior and affected denial/failure paths. In an
iCloud-hosted checkout, prefer Docker's locked checks:

```sh
docker build --target verify -t a2a-lab:verify .
```

Also run the extension's documented real-HTTP walkthrough. Use host checks from
`AGENTS.md` when its environment is resident. Preserve user edits and report
evidence and limits. Keep SDK/protocol versions locked unless a compatibility
change is requested; record private decisions outside the Git repository.
