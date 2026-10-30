# Local model adapter

The optional Ollama adapter is implemented in [ollama.py](../../src/a2a_lab/a2a/ollama.py).
Use the [setup guide](local-model-integration.md) to run it with the lunch agents.
Fixture mode remains available without a model.

## Request path

1. The coordinator selects a permitted specialist.
2. The specialist gets its authorized reference notes.
3. The adapter loads the configured role instructions and task guide.
4. The adapter sends an HTTP request to local Ollama.
5. The adapter does checks of the response format and size.
6. The application attaches references from the supplied notes.
7. The specialist returns an `Answer` through A2A.

The model implements the `KnowledgeLookup.answer(question) -> Answer` domain interface.
The interface keeps SDK wire types out of model code.
The coordinator uses application routing rules rather than a model planner.

## Instructions and context

The `generic` profile loads the base prompt.
The `role` profile also loads the specialist role.
The `guided` profile also loads the specialist task guide.
The loader uses packaged files selected by trusted settings.
Request text cannot select a file path or another role.

A system message contains these instructions.
A separate user message contains the question and reference notes as JSON data.
The model receives no A2A credentials or approval grants.

## Application controls

| Boundary | Implemented behavior |
| --- | --- |
| Network | One configured loopback Ollama endpoint. No implicit proxies or redirects. |
| Time | Inference wait equals one third of the configured request timeout. |
| Output | At most 256 requested output tokens and 2,000 accepted characters. Empty or incomplete responses fail. |
| References | Application code keeps the known note references. The model cannot supply a new trusted source. |
| Failure | No automatic retry or silent fixture substitution. |
| Cancellation | Cancellation ends the HTTP wait. Remote inference can continue. |
| Access | Existing user, service, task ownership, and approval rules remain in application code. |

These controls do not prove that an answer is correct or resistant to prompt injection.
Model text cannot select credentials, add destinations, or authorize an action.

## Extension guidelines

Keep fixture mode for repeatable tests.
Keep model-specific HTTP code inside the adapter.
Do checks of external data before returning an `Answer`.
Keep references tied to authorized source data.
Do not execute generated code, links, or approval flags.

Before a model or runtime change, record its version and model identifier.
Examine its license and source.
Measure response time, memory use, invalid output, and cancellation behavior on the target machine.
Use model evaluations in addition to application policy tests.

The current Docker setup has no approved connection to host inference.
A container inference service needs explicit network, resource, and access controls.
Use the [constitution](../constitution.md) for project requirements.
