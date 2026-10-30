# Lab 4: Extend the maintained boilerplate

This exercise uses the original engineering scenario.
For the Food, Place, and Budget presentation example, use [Lab 7](../07-interactive-review/README.md).
A runbook in this exercise is a written guide for service support.

Create a fixture agent behind the existing domain port and preserve protocol
and security boundaries. The worked `ReleaseReadinessAgent` is already checked
in, so this exercise works from a standalone clone.

## Follow the extension path

1. Read the [constitution](../../docs/constitution.md),
   [implementation skill](../../.agents/skills/a2a-implementation/SKILL.md), and
   [reuse guide](../../docs/guides/boilerplate.md).
2. Inspect `domain/ports.py` and `domain/models.py`: a workflow accepts a question
   and returns bounded `Answer` data, with known citations and no SDK types.
3. Compare `agents/readiness.py` and `agents/knowledge.py`. The new class loads
   `agents/notes/release-readiness.md` and matches relevant words. Shared
   `agents/fixtures.py` retains `[slow]`/`[fail]` teaching controls.
4. Trace the literal `knowledge_workflow` setting into `bootstrap.py`. Startup
   configuration selects behavior; a message cannot change it.
5. Inspect `a2a/cards.py`: description/examples and `required_skill_id` agree
   with the chosen workflow. The client checks this capability before RPC.
6. Reuse the server, executor, task store, identity middleware, approvals, and
   destination policy. There is no extra transport or copied template tree.

`knowledge` remains the network/security role; `release-readiness` is its
selected agent implementation and advertised capability. This does not add a
third network identity. Coordinator still delegates once to the approved peer
with its scoped service token. The reuse guide explains third-peer wiring.

## Run the worked extension

Use a separate Docker project to keep this exercise's state distinct:

```sh
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml up --build -d --wait
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml run --rm client call --text "What should we review before a release?"
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml logs coordinator knowledge
```

Expect discovery of `engineering-coordination`, delegation to `release-readiness`,
and a completed SDK task citing that fixture. The checklist explicitly does not
inspect a system, approve release, or deploy anything. All processes use the same
trusted workflow setting. No new authority is carried in the question.

Demonstrate a capability mismatch before invocation:

```sh
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml run --rm -e A2A_LAB_KNOWLEDGE_WORKFLOW=notes client call --agent knowledge --text "release readiness"
```

Expect exit 1 after discovery, with no `rpc.send` event: the endpoint is approved
but its capability does not match the client's expectation.

```sh
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml run --rm client call --text "[fail] release readiness"
docker build --target verify -t a2a-lab:verify .
```

The fail command returns a controlled failed task/exit 1. Checks cover unsupported
input/operations and existing security controls. Also ask the fixture to change
policy: its fixed answer does not echo or execute instructions. This is fixture
behavior, not model injection resistance.

## Add your own fixture

Choose a small informational capability and stable citation. Add its note and
`KnowledgeLookup` implementation using the worked example. Add a literal setting
choice, bootstrap branch, and truthful card/expected capability; keep deployment
settings and examples consistent. Test useful answers, unrelated input, capability
mismatch, and affected failure paths. Rebuild and exercise it over real HTTP.

Do not let fixture text grant approval, choose URLs, or change identity. Reuse
the exact-term application control for consequential actions. For optional
inference, follow the [model boundary](../../docs/guides/local-model-adapter.md).

## Host option and cleanup

With a resident host environment, run
`A2A_LAB_KNOWLEDGE_WORKFLOW=release-readiness uv run --locked a2a-lab demo --text "release readiness"`.
Add `--secure` with valid host credentials. Manual terminals must share the
setting; the supervised demo propagates it and owns child cleanup.

```sh
docker compose -p a2a-lab-readiness -f compose.yaml -f compose.readiness.yaml down
```

For deliberate reset of credentials and saved operator files, add `--profile tools`
to the Compose options and `--volumes` to `down`. Credentials expire after one hour; see the
[Docker reset guide](../02-docker-delegation/README.md#rebuild-expiry-and-teardown).
