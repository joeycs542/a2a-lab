# Lab 8: Role instructions and task guides

## Goal

Compare three prompt profiles with the same model, lunch notes, and question.
Observe how different instructions can change each specialist's answer.
A successful A2A task does not prove that a generated answer is useful or correct.

Complete the [local model setup](../../docs/guides/local-model-integration.md) first.
Keep Ollama running with `qwen3:0.6b` installed.
Run commands from the repository root with Python 3.12.13 and the locked environment.

## Three meanings of skills

| Object | Consumer | Purpose |
| --- | --- | --- |
| [Coding skill](../../.agents/skills/a2a-implementation/SKILL.md) | Agent that maintains this repository | Instructions for source changes. These instructions do not automatically reach the runtime model. |
| [Runtime role and task guide](../../src/a2a_lab/agents/runtime_prompts/) | Local model | Packaged instructions that the adapter loads explicitly. |
| Agent Card skill | A2A client and coordinator | Description of an advertised task type. It does not grant access. |

The runtime guides are Markdown instruction files.
They have no tools or execution permissions.
They do not implement an external skill-discovery standard.

## Inspect model inputs

Read the [prompt loader](../../src/a2a_lab/agents/prompting.py) and [Ollama adapter](../../src/a2a_lab/a2a/ollama.py).

| Profile | Loaded instructions |
| --- | --- |
| `generic` | Base prompt. |
| `role` | Base prompt and specialist role. |
| `guided` | Base prompt, specialist role, and task guide. This is the default. |

The system message contains the selected instructions.
A separate user message contains the question and retrieved notes as JSON data.
Request text cannot select a role, file, endpoint, credential, or tool.
The coordinator continues to use configured topic matching and application policy.
References identify supplied notes, not independently verified claims.
The instructions request concise answers rather than private reasoning.

## Compare real A2A calls

Stop native A2A services that already use ports 8101–8110.
Choose an unused credential directory.
Install the package and initialize credentials:

```sh
uv sync --locked --no-editable --reinstall-package a2a-lab
uv run --no-editable a2a-lab init-security --discovery --directory .runtime/prompt-lab
```

Run each profile with the same lunch question:

```sh
for profile in generic role guided; do
  echo "Prompt profile: $profile"
  A2A_LAB_DEMO_SCENARIO=team-lunch \
    A2A_LAB_INFERENCE_BACKEND=ollama \
    A2A_LAB_PROMPT_PROFILE="$profile" \
    A2A_LAB_CREDENTIALS_DIRECTORY=.runtime/prompt-lab \
    A2A_LAB_DISCOVERY_MODE=review \
    A2A_LAB_REQUEST_TIMEOUT_SECONDS=120 \
    A2A_LAB_MAX_TASK_POLLS=1000 \
    uv run --no-editable a2a-lab demo --discovery \
    --text "Plan a team lunch: food, place, and budget."
done
```

Each command starts and stops its owned agents.
Do not run profiles concurrently on the same ports.
Credentials expire after one hour.

Compare the results:

1. Does Food answer only its assigned part?
2. Does Place use places from its notes?
3. Does Budget keep the stated spending limits?
4. Does any agent claim to have made a purchase or reservation?
5. Does the coordinator preserve the source of each accepted answer?

Use `Suggest food for our team lunch.` for a one-specialist comparison.
Keep the model and question fixed between profiles.
The temperature is 0.2, so output can still vary.
One good answer does not prove a general improvement.

## Browser exercise

Start one profile on port 8081:

```sh
A2A_LAB_DEMO_SCENARIO=team-lunch A2A_LAB_PROMPT_PROFILE=guided \
  A2A_LAB_WEB_PORT=8081 A2A_LAB_WEB_ORIGIN=http://127.0.0.1:8081 \
  uv run --no-editable python scripts/local-model-web.py
```

Open http://127.0.0.1:8081/.
The footer identifies the profile.
To stop the launcher, press Ctrl-C.
Start it again with `generic` or `role` for comparison.
Restarting clears browser sessions and replay records.

## Extend one guide

Edit the Food [task guide](../../src/a2a_lab/agents/runtime_prompts/skills/food.md).
Change one instruction at a time.
Reinstall the package and restart the demo to load the changed resource.
Do the same comparison again.
Keep maintained prompts and lab instructions in Git.
Keep private discussions outside Git under the [constitution](../../docs/constitution.md#project-documentation-and-private-design-discussions).

Prompts can change output, but application code controls access.
A better instruction does not replace destination checks, task ownership, or approval controls.
Small models can still invent facts, refuse useful requests, or copy instructions.
