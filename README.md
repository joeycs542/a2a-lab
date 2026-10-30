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

Alice and Bob are simulated users of the same browser client. Alice may consult
Operations, Security and Release; Bob may consult Operations and Release. The
coordinator delegates with the requesting user's permissions, so Bob's three-topic
review is incomplete because Security is not permitted. The browser never receives
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

## Team lunch presentation demo

Use a familiar example with three agents: Food, Place, and Budget.
Alice is the lunch organizer. Bob is an attendee without access to the budget.
Ask both users the same question to show the access difference.

For the fixture version, use these files:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml up --build -d --wait
```

Open http://127.0.0.1:8080/. Stop another browser demo on that port first.
Ask “Plan a team lunch: food, place, and budget.”
Alice can receive three answers. Bob can receive Food and Place answers only.
The data is fictional. No order, booking, or payment occurs.
Use the same project name and files for cleanup.

The native model launcher below uses this lunch example by default.
The original engineering scenario remains available for Labs 1–8.
The lunch scenario reuses the existing service IDs: `runbook` for Food, `security` for Budget, and `release` for Place.
Its Agent Cards advertise lunch capabilities. Its reference notes and prompts also use the lunch topics.
The fixed service IDs preserve the existing credential and endpoint boundaries.
Set `A2A_LAB_DEMO_SCENARIO=engineering` when you start the model launcher to use that scenario.

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
- [Lab 8: Runtime prompts and task guidance](labs/08-runtime-prompts/README.md)
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

Open http://127.0.0.1:8080/. Try “Suggest food for our team lunch.”
Then select **Plan the whole lunch**. Stop with Ctrl-C; the launcher stops its agent children
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

### Runtime prompts and task guidance

The model version defaults to `A2A_LAB_PROMPT_PROFILE=guided`: a shared base
prompt, a specialist role prompt, and its task guide are explicitly loaded from
`src/a2a_lab/agents/runtime_prompts/`. Set the profile to `generic` or `role` to
compare the same model and questions with fewer instructions. The browser footer
identifies the selected profile. Restart the native launcher after changing it.

Follow [Lab 8](labs/08-runtime-prompts/README.md) for a three-profile A2A comparison
and a guide-editing exercise. Runtime guides differ from repository coding skills
and advertised A2A capabilities; none grants execution authority.
