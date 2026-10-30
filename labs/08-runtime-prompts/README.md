# Lab 8: Give a local-model agent a role and task guidance

## Goal

Compare three prompt profiles using the same model, reference notes, question,
and A2A delegation flow. Observe that a successful protocol task does not prove
that its generated answer is useful or correct.

Complete the [local-model setup](../../README.md#optional-local-model-version-ollama)
first. Keep Ollama running with `qwen3:0.6b` installed. Run commands from the
repository root, using Python 3.12.13 and the locked environment.

## Three different meanings of skills

| Material | Consumer | Effect |
| --- | --- | --- |
| [Coding skills](../../.agents/skills/a2a-implementation/SKILL.md) | Coding agent maintaining this repository | Engineering instructions; not automatically sent to the runtime model |
| [Runtime role prompts and task guidance](../../src/a2a_lab/agents/runtime_prompts) | Local model, explicitly loaded by the adapter | Shapes each specialist's generated contribution |
| A2A Agent Card skills | A2A clients and the coordinator | Advertises capabilities for discovery; does not contain model instructions or grant permission |

The runtime task guides are ordinary packaged Markdown instructions, not an
implementation of an external skill-discovery standard. They have no tools or
execution permissions.

## Inspect what reaches the model

Read [the prompt loader](../../src/a2a_lab/agents/prompting.py) and
[Ollama adapter](../../src/a2a_lab/a2a/ollama.py).

- `generic`: the shared base prompt, matching the original generic behavior.
- `role`: base prompt plus the configured specialist's role and scope.
- `guided`: base prompt, role, and that specialist's task checklist (the default).

The system message contains the selected packaged instructions. A separate user
message carries the question and retrieved note as JSON data. Request text cannot
select a role, prompt file, endpoint, credentials, or extra tools. The coordinator
still uses keyword routing and application policy. References identify supplied
notes; they do not verify the generated claims. The guides request concise
answers, not private reasoning or a chain of thought.

## Compare through real A2A calls

Stop any native A2A demo using agent ports 8101–8110 first; the Docker fixture demo
can stay running because its agent ports are internal. Choose a new credential
directory if `.runtime/prompt-lab` already exists.

```sh
uv sync --locked --no-editable --reinstall-package a2a-lab
uv run --no-editable a2a-lab init-security --discovery --directory .runtime/prompt-lab

for profile in generic role guided; do
  echo "Prompt profile: $profile"
  A2A_LAB_DEMO_SCENARIO=engineering \
    A2A_LAB_INFERENCE_BACKEND=ollama \
    A2A_LAB_PROMPT_PROFILE="$profile" \
    A2A_LAB_CREDENTIALS_DIRECTORY=.runtime/prompt-lab \
    A2A_LAB_DISCOVERY_MODE=review \
    A2A_LAB_REQUEST_TIMEOUT_SECONDS=120 \
    A2A_LAB_MAX_TASK_POLLS=1000 \
    uv run --no-editable a2a-lab demo --discovery \
    --text "Review runbook, security and release readiness."
done
```

Each invocation starts and stops its owned agents. Do not run profiles
concurrently on the same ports. Credentials expire after one hour.

Compare the answers using these questions:

1. Did each specialist contribute its own portion instead of rejecting the entire request?
2. Are the recommendations concrete and supported by its supplied note?
3. Does the answer distinguish suggested checks from checks actually performed?
4. Did it invent commands, approvals, or facts about a real service?
5. Does every accepted result still pass through the coordinator with attributed references?

Repeat with “What belongs in a runbook?” and “What should we check before a release?”
Keep the model and question fixed when comparing profiles. Temperature is 0.2;
outputs can vary, so a single favorable result is not proof of improvement.

## Browser exercise

Run one profile at a time. For example, on port 8081:

```sh
A2A_LAB_DEMO_SCENARIO=engineering A2A_LAB_PROMPT_PROFILE=guided \
  A2A_LAB_WEB_PORT=8081 A2A_LAB_WEB_ORIGIN=http://127.0.0.1:8081 \
  uv run --no-editable python scripts/local-model-web.py
```

The footer identifies the profile. Use Ctrl-C before restarting with `generic`
or `role`. Restarting clears the browser session and replay recording; capture
comparison observations outside the repository if they include private discussions.

## Extend one guide

Edit the Operations [task guide](../../src/a2a_lab/agents/runtime_prompts/skills/runbook.md)
to improve its checklist. Reinstall the package and restart the demo to load the
edited resource. Change only one instruction at a time and repeat the comparison.
Keep maintained prompts and this exercise in Git; keep private design discussions
outside Git, following the [constitution](../../docs/constitution.md#project-documentation-and-private-design-discussions).

Prompts influence behavior; they do not enforce authorization. The application
retains identity, destination, task ownership, output limits and approval checks.
Small models may still refuse useful requests, hallucinate, or echo instructions.
