# Lab 6: Discover and select specialist agents

Run the authenticated M7 extension with three independent A2A specialists and a
read-only directory. The coordinator selects one suitable peer per question;
the directory supplies candidates, while application policy retains permission.
These are deterministic fixtures/rules, with no downloaded model. For browser
interaction and multi-specialist review, continue to [Lab 7](../07-interactive-review/README.md).

## Start a separate discovery project

From the repository root:

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml up --build -d --wait
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client doctor
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client discover --text "runbook security release"
```

The profile is `local-secure`, topology `discovery`. Candidate IDs/capabilities
and live-card viability are shown; `discover` sends no specialist A2A task. A
compatible public card is metadata, not a guarantee of successful execution.
The authenticated directory accepts topic queries only. Raw question text,
upstream bearer values and caller-supplied owners are not forwarded to it.

Directory is `127.0.0.1:8110`; specialists are runbook 8103, security 8104 and
release 8105. Coordinator remains 8101. Knowledge 8102 retains the shared network
namespace and baseline workflow, but is not a catalog candidate. All services
have private, separate credential mounts; no host ports are published. The
initializer alone mounts all seven recipient/operator credential volumes.

Do not reuse a baseline project's credential volumes for this topology: missing
recipients fail closed, and the initializer never silently upgrades/overwrites
existing credentials. The separate project name selects fresh volumes.

## Ask different engineering questions

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --text "What belongs in a runbook?"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --text "How should we design secure delegation?"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --text "What should we review before a release?"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml logs coordinator directory
```

Expected: the answer identifies runbook, security or release respectively, with
its actual fixture reference. Logs show directory search, live-card validation,
`selection.selected` with a keyword-match reason, and one specialist `rpc.send`.
Polling may fetch the card again; that is not another send. Discovery does not
run in the specialist or recursively expand from returned instructions.

Matching counts distinct supported keywords, never card-provided instructions.
Try controlled no-match and ambiguity responses:

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --text "What is the weather?"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --text "security release"
```

The first asks for a supported topic and makes no catalog/peer request. The
second asks the user to choose a topic and sends no specialist task. Both are
completed informational answers with empty references, not fabricated expertise.
Review mode in Lab 7 combines matching authorized specialists into one result.

## Check permissions and availability

The synthetic policy lets Alice use all three specialists. Bob may use runbook
and release; security is Alice-only. Public cards contain general metadata, so
this policy restricts invocation rather than hiding the existence of a service.

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client discover --as bob --text "runbook security release"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --as bob --text "security"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm client call --as bob --agent security --text "security"
```

Bob's search excludes security. His coordinator returns no authorized compatible
specialist; direct security invocation exits nonzero. The peer independently
enforces the owner policy even with a valid recipient token. Directory filtering
alone is not authorization. Operator credentials simulate identities, not real login.

To observe an unavailable candidate without Compose restarting its dependencies:

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml stop runbook
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm --no-deps client call --text "runbook"
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml start runbook
```

The coordinator excludes the unreachable live card and reports no viable peer
without sending a task to it. For task/lifecycle operations, open an operator shell:

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml run --rm --entrypoint /bin/sh client
```

Inside the operator shell, `a2a-lab call --async --text "[slow] release"`, `task get`
and `task cancel` work as in [Lab 3](../03-secure-delegation/README.md). Default
delay is two seconds; cancel promptly. For a longer inspection window include
`-f compose.workshop.yaml` on **every** startup/client/cleanup command. Known child
IDs are canceled best-effort; a lost start response can still leave a remote
outcome unknown. The `delegation.started` trace identifies when the client knows
the child ID. Task reads/cancellation retain verified actor/owner scopes.

## Native option and checks

For a resident Python installation, generate a fresh directory and run the owned
multi-process demo. Use that same absolute path for manual serve/call commands:

```sh
uv run a2a-lab init-security --discovery --directory .runtime/discovery-security
A2A_LAB_CREDENTIALS_DIRECTORY="$PWD/.runtime/discovery-security" uv run a2a-lab demo --discovery --text "release readiness"
```

Manual discovery commands require `A2A_LAB_PROFILE=local-secure` and
`A2A_LAB_TOPOLOGY=discovery` in every terminal. Approved catalog membership can be
reduced with `A2A_LAB_DISCOVERY_PEERS='["runbook","release"]'`; set it consistently
in directory/coordinator/client. It cannot add arbitrary identities/endpoints.
The baseline without discovery flags/settings remains the original two-agent lab.

```sh
docker build --target verify -t a2a-lab:verify .
```

Tests cover recipient isolation, filtered search, forged URLs/skills/duplicates,
unsolicited/private candidates, incompatible live cards before RPC, topic routing,
unavailable peers and cancellation of a known selected child. Existing approval,
lifecycle and baseline cases remain included. These tests do not assess LLM prompts.

## Teardown

Exit the operator shell, then delete only this session's teaching state:

```sh
docker compose -p a2a-discovery -f compose.yaml -f compose.discovery.yaml --profile tools down --volumes
```

This removes seven credential volumes plus operator-work. Credentials expire after
one hour; deliberate fresh-volume reset is the recovery procedure. See the
[discovery decision](../../docs/decisions/0009-curated-discovery.md) for design limits.
