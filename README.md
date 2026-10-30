# a2a-lab

A local Python lab for the Agent2Agent (A2A) protocol.
Use a team lunch to see how a coordinator finds agents, sends work, and returns answers.

The coordinator has the supervisor role.
It selects permitted agents and sends the question to each selected agent.
Each specialist returns an answer.
The coordinator puts the answers together for the client.

| Agent | Task |
| --- | --- |
| Food | Give food options from the lunch notes. |
| Place | Give place options from the lunch notes. |
| Budget | Give the spending limits from the lunch notes. |

Alice and Bob are simulated users of the same client.
Alice is the organizer and can use all three agents.
Bob is an attendee and can use Food and Place only.
The directory filters entries for the user.
Each receiving agent also applies its own access rules.

All lunch data is fictional.
The demo makes no purchases or reservations.

## Browser demo

This version uses packaged example data, called fixtures.
It needs Docker Desktop, but it needs no model download or model API key.

From the repository root, start a new named project:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml up --build -d --wait
```

Open http://127.0.0.1:8080/.
Use that exact address.
Only one browser demo can use port 8080 at a time.

1. Select Alice.
2. Ask `Plan a team lunch: food, place, and budget.`
3. Follow discovery, agent selection, question receipt, and the answers.
4. Read the final result above the map.
5. Expand **Specialist work** to read each agent's output.
6. Select Bob.
7. Ask the same question.
8. Compare his partial plan with Alice's full plan.

Bob receives Food and Place answers.
The access rules exclude Budget.
This difference comes from application rules, not from a different model.

After execution, select **Replay**.
Replay starts paused.
Use **Previous step** and **Next step** to examine the recorded events.
Use **Resume** for automatic playback.
Replay makes no new agent or model requests.
The final return path and result appear at the delivery step.

Teaching credentials expire after one hour.
A container restart does not renew them.
For a new session, stop the project and use a new, unused project name.
A server restart discards tasks and browser sessions.

To stop this project and keep its volumes, run:

```sh
docker compose -p a2a-lunch -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml -f compose.lunch.yaml down
```

Use the same project name and Compose files for startup, logs, status, and shutdown.

## Optional local model version (Ollama)

This version uses the same A2A services and access rules.
Each selected specialist makes a separate request to a local model.
The specialists share one model runtime, with different role instructions and task guides.
The coordinator uses configured topic matching.
It does not use a model to select agents.

Use the [local model setup guide](docs/guides/local-model-integration.md) for the complete procedure.
The guide uses Ollama and `qwen3:0.6b`.
The model download is approximately 523 MB.
Runtime memory use is higher.

After Ollama is running and the model is installed, start the native demo:

```sh
uv sync --locked --no-editable
uv run --no-editable python scripts/local-model-web.py
```

Open http://127.0.0.1:8080/.
The native launcher selects the team lunch scenario by default.
Try `Suggest food for our team lunch.`
Then select **Plan the whole lunch**.
The browser footer identifies the model and prompt profile.

If another demo uses port 8080, use port 8081:

```sh
A2A_LAB_WEB_PORT=8081 A2A_LAB_WEB_ORIGIN=http://127.0.0.1:8081 \
  uv run --no-editable python scripts/local-model-web.py
```

To stop the demo, press Ctrl-C.
The launcher stops its child services and removes its temporary credentials.
Restart the launcher after the one-hour credential lifetime.

The isolated Docker services cannot reach host Ollama.
Use the native launcher for local inference.
The model guide describes time limits, output limits, and failure behavior.
Examine generated answers before real use.

### Runtime prompts and task guidance

The default prompt profile is `guided`.
It loads the base prompt, the specialist role, and the specialist task guide.
The files are in [runtime_prompts](src/a2a_lab/agents/runtime_prompts/).
Use `generic` or `role` to compare answers with fewer instructions.
Restart the launcher after a profile change.

[Lab 8](labs/08-runtime-prompts/README.md) uses the lunch agents for this comparison.
Runtime instructions differ from repository coding skills and Agent Card skills.
None of these objects grants access.

## Configuration

| Setting | Meaning |
| --- | --- |
| `A2A_LAB_DEMO_SCENARIO` | `team-lunch` or `engineering`. General settings default to `engineering`. The native model launcher defaults to `team-lunch`. |
| `A2A_LAB_INFERENCE_BACKEND` | `fixture` or `ollama`. General settings default to `fixture`. The native model launcher selects `ollama`. |
| `A2A_LAB_OLLAMA_MODEL` | Local model tag. Default: `qwen3:0.6b`. |
| `A2A_LAB_OLLAMA_PORT` | Loopback Ollama port. Default: `11434`. |
| `A2A_LAB_PROMPT_PROFILE` | `generic`, `role`, or `guided`. Default: `guided`. |
| `A2A_LAB_WEB_PORT` | Browser port. Default: `8080`. |
| `A2A_LAB_WEB_ORIGIN` | Exact browser origin. Its port must match the browser port. |

Use [Settings](src/a2a_lab/config.py) for all fields and limits.
The lunch scenario requires the discovery topology.
Use `compose.lunch.yaml` with the other files in the browser command above.

## Original engineering labs

Labs 1–6 retain their original engineering exercises.
They teach protocol operations, access rules, human approval, and code extension.
A runbook in those exercises means a written guide for service support.
These exercise terms do not name the lunch agents shown in the main demo.

The lunch scenario keeps fixed internal service IDs for compatibility:

| Internal service ID | Lunch name | Lunch Agent Card skill | Original engineering name |
| --- | --- | --- | --- |
| `runbook` | Food | `lunch-food` | Operations |
| `release` | Place | `lunch-place` | Release |
| `security` | Budget | `lunch-budget` | Security |

Service IDs appear in commands, ports, and credential rules.
They do not change the lunch task guides or the advertised lunch skills.

To use the original browser scenario, omit `compose.lunch.yaml` from its startup and shutdown commands.
To use it with the native model launcher, set `A2A_LAB_DEMO_SCENARIO=engineering`.

The baseline CLI uses the original two-agent setup:

```sh
docker compose up --build -d --wait
docker compose run --rm client call
docker compose down
```

## Python development

Use Python 3.12.13 and `uv`:

```sh
uv sync --locked
uv run a2a-lab doctor
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```

For an equivalent locked check in Docker, run:

```sh
docker build --target verify -t a2a-lab:verify .
```

For the browser logic check, use Node.js:

```sh
node scripts/web-ui-smoke.cjs
```

After source changes in a cloud-synced macOS folder, reinstall the package before execution:

```sh
uv sync --locked --no-editable --reinstall-package a2a-lab
```

## Labs and guides

Start with Lab 7 for the lunch demo.
Use Lab 8 for local model prompts.
The earlier labs use the original engineering examples.

- [Lab 1: Local delegation](labs/01-local-delegation/README.md)
- [Lab 2: Docker delegation](labs/02-docker-delegation/README.md)
- [Lab 3: Secure delegation](labs/03-secure-delegation/README.md)
- [Lab 4: Package extension](labs/04-boilerplate-extension/README.md)
- [Lab 5: Agent Cards](labs/05-agent-cards/README.md)
- [Lab 6: Agent discovery](labs/06-agent-discovery/README.md)
- [Lab 7: Team lunch browser demo](labs/07-interactive-review/README.md)
- [Lab 8: Runtime prompts and task guidance](labs/08-runtime-prompts/README.md)
- [Local model setup](docs/guides/local-model-integration.md) and [adapter guide](docs/guides/local-model-adapter.md)
- [Workshop guide](docs/guides/workshop.md), [handoff guide](docs/guides/handoff.md), and [reuse guide](docs/guides/boilerplate.md)
- [Security reference](docs/security.md), [project constitution](docs/constitution.md), and [documentation guide](docs/guides/documentation.md)
- [Implementation skill](.agents/skills/a2a-implementation/SKILL.md) and [Agent Card skill](.agents/skills/a2a-agent-card/SKILL.md)
