# a2a-lab

A local Python lab demonstrating Agent2Agent (A2A) discovery, delegation,
owner-scoped tasks and cancellation. The agents use bundled synthetic fixtures;
no model download or API key is required.

## Browser demo

With Docker Desktop running, start a fresh named Compose project:

```sh
docker compose -p a2a-demo -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml up --build -d --wait
```

Open http://127.0.0.1:8080/ using that exact address. Run the default single-agent
question or choose the three-specialist review. Replay starts paused; use Resume,
Previous step and Next step to inspect the recorded execution. The final response
appears above the map; specialist processing summaries and findings expand below.

Alice and Bob are synthetic identities. Security guidance is Alice-only; Bob's
three-specialist review returns an incomplete result. The browser never receives
bearer credentials. These informational fixtures do not inspect real systems,
approve releases or execute actions.

Teaching credentials expire one hour after creation. Restarting containers does
not renew them. Stop the current project and choose a new, unused project name
for a fresh session. Only one browser demo can use host port 8080 at a time.
Server restarts discard in-memory tasks and sessions.

Stop the project while preserving its volumes:

```sh
docker compose -p a2a-demo -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml down
```

Use the same project name and Compose files for status, logs and teardown.

## Baseline CLI demo

```sh
docker compose up --build -d --wait
docker compose run --rm client call
docker compose down
```

## Python development

Python 3.12.13 and `uv` are required for native development:

```sh
uv sync --locked
uv run a2a-lab doctor
uv run a2a-lab demo
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

Alternatively, run the locked checks in Docker:

```sh
docker build --target verify -t a2a-lab:verify .
```

The dependency-free browser logic check requires Node.js:

```sh
node scripts/web-ui-smoke.cjs
```

## Labs and guides

- [Lab 1: Local delegation](labs/01-local-delegation/README.md)
- [Lab 2: Docker delegation](labs/02-docker-delegation/README.md)
- [Lab 3: Secure delegation](labs/03-secure-delegation/README.md)
- [Lab 4: Boilerplate extension](labs/04-boilerplate-extension/README.md)
- [Lab 5: Agent Cards](labs/05-agent-cards/README.md)
- [Lab 6: Agent discovery](labs/06-agent-discovery/README.md)
- [Lab 7: Interactive review](labs/07-interactive-review/README.md)
- [Workshop guide](docs/guides/workshop.md), [handoff guide](docs/guides/handoff.md),
  and [reuse guide](docs/guides/boilerplate.md)
- [Security reference](docs/security.md) and [project constitution](docs/constitution.md)
- [Implementation skill](.agents/skills/a2a-implementation/SKILL.md) and
  [Agent Card skill](.agents/skills/a2a-agent-card/SKILL.md)

## Optional local model version (Ollama)

The default demo above stays deterministic. This opt-in version uses the same
A2A servers, discovery, supervisor, task lifecycle and permissions. Each specialist
calls a local model using its bundled synthetic note as context. The coordinator
still routes by keywords and collects attributed answers; it is not an LLM planner.
All specialists share one model runtime, with separate requests and role context.
The UI identifies the model and shows workflow summaries, not private reasoning.

Install [Ollama](https://ollama.com/download), then in a terminal:

```sh
ollama serve
```

If the Ollama app is already running, its server is already available. In another
terminal download the small [Qwen3 0.6B model](https://ollama.com/library/qwen3:0.6b)
(about 523 MB of weights; runtime memory use is higher), and warm it up:

```sh
ollama pull qwen3:0.6b
ollama run qwen3:0.6b --think=false "Say ready in one word."
```

Run the model version **natively**, from this repository with Python 3.12.13 and
`uv`. The existing isolated Docker stack cannot reach the host Ollama server;
these commands deliberately use a separate native launch path.

```sh
uv sync --locked --no-editable
uv run --no-editable python scripts/local-model-web.py
```

Open http://127.0.0.1:8080/. Try “What belongs in a runbook?” and then the
three-specialist review. Stop with Ctrl-C; the launcher stops its agent children
and removes its temporary teaching credentials. Restart after the one-hour
credential lifetime. Stop the existing Docker browser demo first, or use another
browser port:

```sh
A2A_LAB_WEB_PORT=8081 A2A_LAB_WEB_ORIGIN=http://127.0.0.1:8081 \
  uv run --no-editable python scripts/local-model-web.py
```

For a one-shot supervisor/delegation exchange without the browser, create fresh
credentials in an unused directory first:

```sh
uv run --no-editable a2a-lab init-security --discovery --directory .runtime/model-cli
A2A_LAB_CREDENTIALS_DIRECTORY=.runtime/model-cli \
  A2A_LAB_INFERENCE_BACKEND=ollama A2A_LAB_REQUEST_TIMEOUT_SECONDS=120 \
  A2A_LAB_MAX_TASK_POLLS=1000 uv run --no-editable a2a-lab demo --discovery \
  --text "What belongs in a runbook?"
```

To use another locally installed text model, set `A2A_LAB_OLLAMA_MODEL` to its
Ollama tag. `A2A_LAB_OLLAMA_PORT` changes the loopback inference port (default
11434). No model is downloaded automatically; no cloud API key is used. Only the
question and bundled note are sent to Ollama, without A2A credentials. Do not use
cloud model tags if you want inference to stay local.

The launcher allows 120 seconds per root task; each specialist's inference wait
is bounded to 40 seconds and output to 256 tokens / 2000 characters. Small models
may hallucinate; references identify supplied context, not independently verified
claims. Unsupported topics return the existing no-match explanation without
calling a model. Missing models, unavailable Ollama, invalid output or exceeded
budgets fail explicitly, with no silent fixture fallback. For slow hardware,
start with one specialist and warm the model before presenting. Cancellation stops
the application's HTTP wait; Ollama may continue inference server-side.

Return to the original version by running the normal Docker command, or leave
`A2A_LAB_INFERENCE_BACKEND=fixture` for native commands. After editing source on
cloud-synced macOS folders, reinstall with `uv sync --locked --no-editable --reinstall-package a2a-lab` before
running the installed package.
