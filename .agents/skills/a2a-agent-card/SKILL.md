---
name: a2a-agent-card
description: Define or review Agent Cards for this lab's pinned A2A Python SDK. Use when changing advertised capabilities, workflow selection, endpoints, content modes, examples, or authentication declarations.
---

# A2A Agent Card

Read the [constitution](../../../docs/constitution.md) and the
[pinned SDK reference](references/sdk-1.2.2.md). Change the typed factory in
`src/a2a_lab/a2a/cards.py`; do not paste an older tutorial's schema into it.
Coding `SKILL.md` files guide engineering; `AgentSkill` objects describe runtime
behavior. Neither grants identity, destination access, or action authority.

## Review from behavior to declaration

Inspect the selected workflow, domain result, bootstrap, executor, served routes,
and profile before declaring capabilities. Describe the fixture's actual limits:
the readiness checklist does not inspect systems or approve deployment.

Check stable IDs, metadata, tags, and runnable examples. Update the trusted
expected skill selector when changing behavior, so unsuitable peers are rejected
before RPC. Card text cannot replace the chosen role/endpoint. Content modes
must match input validation and typed result artifacts.

For discovery, bind each fixed specialist to its configured capability and
recipient. The coordinator advertises `engineering-discovery` in single mode
or `engineering-review` in review mode. Validate that selection on the live
card; catalog prose cannot change it. Directory search and discovery traces
are separate application APIs, not extra A2A methods or protocol streaming.

Keep installed application version separate from interface protocol version.
Derive the one JSON-RPC `1.0` endpoint from `Settings`. Advertise streaming,
push, extended cards, or signing only after implementing and verifying them.
A security declaration or signature is not proof of enforcement.

For `local-secure`, match the actual bearer middleware and named scheme without
publishing tokens, digests, private policy, or operator accounts. Keep security
requirements absent in `local-demo`. An auth description cannot loosen route,
audience, or ownership policy.

## Validate the served contract

Use the official resolver/client and SDK serialization. Check the configured
endpoint, selected skill, examples, content modes, profile, and secret-free card
over HTTP. Test missing/incompatible capabilities and endpoint changes before
delegation, plus unsupported inputs and operations at the server.

Use the [card exercise](../../../labs/05-agent-cards/README.md) and existing
contract/security tests. Record served and exercised behavior; do not describe
planned registries, models, or security features as implemented.
