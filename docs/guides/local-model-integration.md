# Local model setup

The Ollama adapter is implemented.
The native launcher uses the team lunch scenario and the `guided` prompt profile by default.
It starts real A2A services with temporary teaching credentials.

The coordinator selects agents through configured topic matching and access rules.
Food, Place, and Budget make separate requests to the same model runtime.
Their role instructions and task guides differ.
Alice can use all three agents.
Bob can use Food and Place only.

## Requirements

Use Python 3.12.13, `uv`, and a local [Ollama installation](https://ollama.com/download).
Run commands from the repository root.
Stop native A2A services that already use agent ports 8101–8110.
The Docker fixture demo uses private agent ports, but its browser can still occupy port 8080.

Keep Ollama on loopback.
The adapter connects to `127.0.0.1:11434` by default.
It does not use a cloud API key.

## Start Ollama

If the Ollama application already serves port 11434, use that server.
Otherwise, start a local server:

```sh
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
```

In another terminal, download the model:

```sh
ollama pull qwen3:0.6b
```

The download is approximately 523 MB.
The runtime needs more memory than the model file.
Response time and answer quality depend on the machine and question.

Before the demo, load the model with a short request:

```sh
ollama run qwen3:0.6b --think=false "Say ready in one word."
```

## Start the lunch demo

Install the locked environment:

```sh
uv sync --locked --no-editable
```

Start the native launcher:

```sh
uv run --no-editable python scripts/local-model-web.py
```

Open http://127.0.0.1:8080/.
Ask `Suggest food for our team lunch.`
Then select **Plan the whole lunch**.
Compare Alice and Bob with the same question.
The footer identifies the active model and prompt profile.

If port 8080 is in use, start the browser on port 8081 instead:

```sh
A2A_LAB_WEB_PORT=8081 A2A_LAB_WEB_ORIGIN=http://127.0.0.1:8081 \
  uv run --no-editable python scripts/local-model-web.py
```

To stop the launcher and its child services, press Ctrl-C.
The launcher removes its temporary credentials on exit.
Credentials expire after one hour.
Restart the launcher for a new session.

## One request without the browser

Choose an unused credential directory.
Initialize the credentials:

```sh
uv run --no-editable a2a-lab init-security --discovery --directory .runtime/lunch-cli
```

Run one lunch request:

```sh
A2A_LAB_CREDENTIALS_DIRECTORY=.runtime/lunch-cli \
  A2A_LAB_DEMO_SCENARIO=team-lunch \
  A2A_LAB_INFERENCE_BACKEND=ollama \
  A2A_LAB_DISCOVERY_MODE=review \
  A2A_LAB_REQUEST_TIMEOUT_SECONDS=120 \
  A2A_LAB_MAX_TASK_POLLS=1000 \
  uv run --no-editable a2a-lab demo --discovery \
  --text "Plan a team lunch: food, place, and budget."
```

The command starts and stops its owned agents.
It does not remove the credential directory that you created.
Do not run it while the native browser launcher uses the same agent ports.

## Model and prompt settings

| Setting | Use |
| --- | --- |
| `A2A_LAB_OLLAMA_MODEL` | Select another installed local text model by its Ollama tag. |
| `A2A_LAB_OLLAMA_PORT` | Select the loopback inference port. Default: `11434`. |
| `A2A_LAB_PROMPT_PROFILE` | Select `generic`, `role`, or `guided`. Default: `guided`. |
| `A2A_LAB_DEMO_SCENARIO` | Select `team-lunch` or the original `engineering` example. |

Do not use a cloud model tag for local inference.
The lab does not download models automatically.
Restart the launcher after a settings change.
Use [Lab 8](../../labs/08-runtime-prompts/README.md) to compare prompt profiles.

## Limits and failure behavior

The native launcher allows 120 seconds for a root task.
Each specialist allows 40 seconds for inference under this setting.
The adapter requests at most 256 output tokens and accepts at most 2,000 output characters.
It uses a context limit of 4,096 tokens.
It sends the question, selected instructions, and authorized example notes to Ollama.
It does not send A2A credentials.

The application attaches references from the supplied notes.
These references do not prove the accuracy of generated claims.
An unsupported question can return a no-match answer without a model request.
A missing model, unavailable server, invalid answer, or exceeded limit causes an explicit failure.
The adapter does not silently substitute fixture output.

Cancellation stops the application's HTTP wait.
Ollama can continue work that it already started.
A timeout does not prove that remote generation stopped.

The isolated Docker services cannot reach host Ollama.
Use the native launcher for this setup.
Do not expose Ollama on all network interfaces to connect the existing containers.

For repeatable answers without a model, use the [Docker lunch demo](../../README.md#browser-demo).
For implementation details, read the [adapter guide](local-model-adapter.md).

## Source changes

After a source or prompt change, reinstall the package:

```sh
uv sync --locked --no-editable --reinstall-package a2a-lab
```

Restart the launcher to load the changed files.
