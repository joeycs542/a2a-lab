# Lab handoff

This repository contains one Python package, eight labs, two coding skills, and maintained project guides.
The main presentation example is a team lunch.
The earlier protocol exercises retain their original engineering examples.

## First session

Start with the [README browser demo](../../README.md#browser-demo).
It uses packaged lunch notes without a model.
Use [Lab 7](../../labs/07-interactive-review/README.md) for the complete walkthrough.

The coordinator has the supervisor role.
It finds permitted Food, Place, and Budget agents, sends work, and puts their answers together.
Alice can use all three agents.
Bob can use Food and Place only.
The directory and receiving agents apply independent access checks.

Use the same project name and Compose files for startup, logs, status, and shutdown.
Create teaching credentials shortly before the session.
They expire after one hour.
A restart does not renew them.
For a new session, stop the project and use a new, unused project name.

The browser can replay recorded events after a request.
Replay starts paused and makes no new network requests.
The final result appears above the map at delivery.
The lower disclosures show individual specialist output.
A server restart loses tasks, browser sessions, and replay records.

## Learning path

| Goal | Starting point |
| --- | --- |
| Explain discovery and the supervisor role with lunch agents | [Lab 7](../../labs/07-interactive-review/README.md). |
| Run a small local model | [Local model setup](local-model-integration.md). |
| Compare runtime instructions | [Lab 8](../../labs/08-runtime-prompts/README.md). |
| Follow the original two-agent protocol exchange | [Lab 1](../../labs/01-local-delegation/README.md) and [Lab 2](../../labs/02-docker-delegation/README.md). |
| Exercise task ownership and human approval | [Lab 3](../../labs/03-secure-delegation/README.md) and [workshop](workshop.md). |
| Add a task type | [Lab 4](../../labs/04-boilerplate-extension/README.md) and [reuse guide](boilerplate.md). |
| Inspect an Agent Card | [Lab 5](../../labs/05-agent-cards/README.md). |
| Exercise single-specialist selection and failures | [Lab 6](../../labs/06-agent-discovery/README.md). |

The original two-agent setup uses a coordinator and a knowledge agent.
Its `notes` and `release-readiness` workflows share the knowledge service identity.
The discovery setup adds a directory and three specialist identities.
The lunch scenario changes their displayed names, skills, notes, and prompts.
It preserves the fixed internal service IDs and credential boundaries.

## Local model behavior

The Ollama adapter is implemented.
The native launcher selects the lunch scenario and the `guided` profile by default.
Each permitted specialist makes a separate request to the same model runtime.
The coordinator uses configured topic matching rather than a model planner.

The isolated Docker services cannot reach host Ollama.
Use the native launcher for this model setup.
Use fixture mode for repeatable answers without a model.
Generated answers require examination before real use.
A2A streaming, push notifications, open registration, and Agent Card signature verification are not implemented.

## Contributor checks

Use the locked native environment:

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

For the equivalent Docker verification, run:

```sh
docker build --target verify -t a2a-lab:verify .
```

For the browser logic check, run:

```sh
node scripts/web-ui-smoke.cjs
```

Dependency installation needs access to package or image sources.
The Docker verification command disables external networking while preserving loopback for integration tests.
Use the [pinned SDK reference](../../.agents/skills/a2a-agent-card/references/sdk-1.2.2.md) before a dependency update.

[GitHub Actions](../../.github/workflows/lab-ci.yaml) runs locked checks, Compose validation, and installed CLI and HTTP smoke checks.
It uses read-only repository permissions.
It does not deploy the lab, publish an image, or install a model.
Local checks do not prove that a hosted Actions run passed.

## Scope and project rules

Read the [security guide](../security.md) for access controls and deployment limits.
This is a local teaching lab with simulated users and in-memory state.
It does not provide a complete production identity system or proof of model prompt resistance.
The lunch demo makes no purchases or reservations.
Lab 3 approval produces only a simulated local-display receipt.

Use the [constitution](../constitution.md) for project rules.
Use [AGENTS.md](../../AGENTS.md) and the [coding skills](../../.agents/skills/) for source changes.
Write maintained documentation in ASD-STE100 Issue 9.
Keep useful project guides and skills in Git.
Keep private design discussions and presentation materials outside Git.

Django, MCP, procurement, and payment examples are not implemented.
