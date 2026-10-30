# Lab 5: Review a served Agent Card

This exercise uses the original engineering scenario.
For the Food, Place, and Budget presentation example, use [Lab 7](../07-interactive-review/README.md).
A runbook in this exercise is a written guide for service support.

Use the [card skill](../../.agents/skills/a2a-agent-card/SKILL.md) and
[pinned SDK reference](../../.agents/skills/a2a-agent-card/references/sdk-1.2.2.md).
Runtime cards describe capabilities; coding skills guide implementation.
A public card does not establish identity or grant permission.

## Inspect the public contract

```sh
docker compose up --build -d --wait
docker compose run --rm --entrypoint python client -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8102/.well-known/agent-card.json", timeout=2).read().decode())'
docker compose run --rm client call --agent knowledge --text "What information should our service runbook contain?"
```

Compare the served card with actual behavior:

| Check | Expected |
| --- | --- |
| Interface | `http://127.0.0.1:8102/a2a/jsonrpc`, JSON-RPC, protocol `1.0`. |
| Application version | Installed package version, independent of protocol version. |
| Capability | `engineering-knowledge` for notes; `release-readiness` for the extension. |
| Input/output | Text questions; JSON `Answer` artifacts with stable references. |
| Examples | Runnable questions for the selected workflow and deliberate slow/fail fixtures. |
| Authentication | `localBearer` and matching requirement for secure mode; no token/verifier data. |
| Unimplemented features | Streaming, push, extended cards, and signing absent or false. |

Default false protobuf values can be absent in JSON. Absence is not a positive
feature declaration. URLs belong to `supportedInterfaces`, not the older top-level
URL schema. Compare auth declarations using the optional Docker demo profile in
[Lab 2](../02-docker-delegation/README.md), keeping profiles/projects distinct.

## Check denial cases

Run [Lab 4's mismatch command](../04-boilerplate-extension/README.md#run-the-worked-extension)
to refuse a valid but unsuitable card before RPC. Existing tests also reject
changed endpoints, missing skills, incompatible protocol/binding/modes, malformed
JSON, and redirects:

```sh
docker build --target verify -t a2a-lab:verify .
```

`tests/contract/test_extension.py` exercises unadvertised streaming/extended-card
operations and non-text input, expecting protocol errors. Task operations retain
secure identity/ownership checks. Typed construction alone cannot prove a
capability; served behavior and failure checks supply the evidence.

For discussion, locate each enforcement point. What changes would a third peer,
streaming, signing, or a model adapter require? Advertise those features only after
execution, authorization, and failure behavior exist. Stop with `docker compose down`;
resetting volumes is a separate choice.
