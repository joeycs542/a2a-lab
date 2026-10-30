# Engineering lab handoff

This repository contains the reusable Python lab, constitution, two coding skills,
seven exercises, security evidence and optional model integration guidance. The
required demos use fixtures; no models, API keys, Django or MCP server are required.

## First session

Start from a checkout with Docker Desktop running. Run from the repository root:

```sh
docker compose up --build -d --wait
docker compose run --rm client call --text "What belongs in a runbook?"
docker compose logs coordinator knowledge
```

Expect live discovery and coordinator-to-knowledge delegation, followed by a typed
answer and task ID. The first build downloads images and locked dependencies.
Later calls reuse the running agents. Docker keeps dependencies and teaching
credentials outside the host's iCloud-managed Python environment.

Use the [workshop](workshop.md) for a fresh named project and the complete 90-minute
session. Create credentials immediately before the live section; they expire after
one hour. The last 30 minutes are discussion/code review. The optional workshop
override makes manual cancellation easier without changing normal defaults.

Stop normal demo containers with `docker compose down`. This preserves teaching
volumes. To deliberately delete expired credentials and saved operator files:

```sh
docker compose --profile tools down --volumes
```

Use the same project name and Compose files that started the session. Do not reset
another project. Server restart loses task/proposal/grant/receipt state even when
credential and operator-file volumes remain.

## Learning and extension path

| Goal | Starting point |
| --- | --- |
| Understand real local delegation | [Lab 1](../../labs/01-local-delegation/README.md) and [Docker execution](../../labs/02-docker-delegation/README.md). |
| Exercise identity, cancellation and exact human approval | [Lab 3](../../labs/03-secure-delegation/README.md), [workshop](workshop.md), [security evidence](../security.md). |
| Extend domain behavior while reusing controls | [Lab 4](../../labs/04-boilerplate-extension/README.md), [reuse guide](boilerplate.md). |
| Define truthful cards | [Lab 5](../../labs/05-agent-cards/README.md), [Agent Card coding skill](../../.agents/skills/a2a-agent-card/SKILL.md). |
| Search approved specialists and select one | [Lab 6](../../labs/06-agent-discovery/README.md). |
| Interact in a browser and review multiple specialists | [Lab 7](../../labs/07-interactive-review/README.md). |
| Guide future coding agents | [AGENTS.md](../../AGENTS.md), [constitution](../constitution.md), [implementation skill](../../.agents/skills/a2a-implementation/SKILL.md). |
| Evaluate optional inference later | [Adapter boundary](local-model-adapter.md) and [runtime/setup guide](local-model-integration.md). |

The two workflow choices are `notes` and `release-readiness`. They serve the same
knowledge network/security role; neither adds a third identity. The opt-in
discovery topology separately adds three specialist identities and a searchable
curated directory. Streaming, callbacks, open registration, signed cards and
inference remain extensions.

For a presentation, Lab 7 defaults to a single-specialist question and shows the
coordinator's discovery and delegation path. Run live, then replay recorded steps
without network requests; expand the response and execution evidence as needed.
The dependency-free frontend check is `node scripts/web-ui-smoke.cjs` with Node
available on the host. Browser replay is a teaching view of retained traces, not
A2A streaming, a durable recording, or a second agent execution.

## Contributor and CI checks

For a resident native Python environment:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

The equivalent locked Docker checks run with:

```sh
docker build --target verify -t a2a-lab:verify .
```

Dependency installation needs package/image access. The verification stage's
lint/type/test command has networking disabled except container loopback, so live
integration requests remain synthetic and local. Do not change the lockfile just
to obtain a passing install. Check the [pinned SDK reference](../../.agents/skills/a2a-agent-card/references/sdk-1.2.2.md)
before a dependency update.

[GitHub Actions](../../.github/workflows/lab-ci.yaml) runs on pushes, pull requests
and manual dispatch. It uses read-only repository permissions and a full-SHA
checkout action with persisted credentials disabled. It builds the verification
and installed runtime images, exercises both supervised profiles plus the worked
extension without external runtime networking, validates Compose overrides, and
calls independent Compose agents in notes and release-readiness configurations.
It also exercises directory routing and the browser/review HTTP smoke in a separate
project, including partial permissions, session isolation, CSRF and cancellation.
The existing behavioral suite covers positive, denial, failure, cancellation,
ownership, approval integrity and concurrency paths. Cleanup runs even on failure.

CI does not deploy, push an image, install a model or require application secrets.
The workflow is locally validated; a hosted GitHub run can occur after the changes
are committed and pushed to a repository with Actions enabled. Local evidence does
not imply that the hosted runner has already executed it.

## Delivery scope and ownership

Use the checks in this guide to verify a new installation.
This is a loopback teaching lab with synthetic identity,
ephemeral state and deterministic policy checks. Deployment/inference gaps remain
in [security evidence](../security.md); no production readiness or model prompt
resistance is claimed.

Keep private design records and presentation notes outside the Git repository.
A code clone contains the lab instructions and core security guidance.
Do not distribute private material without explicit authorization.

The optional B2B supply chain remains unimplemented. Its planned split is A2A
between agents, scoped MCP tools into Django, and backend enforcement of stock,
price floors, exact approvals and transactional reservations. Start it as a
separate explicitly scoped milestone after the core handoff.

## Runtime prompt exercise

[Lab 8](../../labs/08-runtime-prompts/README.md) compares generic, role-specific,
and guided prompts through the same local-model A2A setup. The fixture path
remains the default; the model launcher uses guided prompts unless overridden.
