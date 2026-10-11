# Integrating local models later

Reviewed: 11 October 2026. **Design and optional setup guidance:** no model or
inference runtime has been installed or connected to the lab. The current CLI
offers `notes` and `release-readiness` fixtures only. Commands below are setup
examples checked against primary documentation, not executed validation.

The existing [adapter design](local-model-adapter.md) defines `KnowledgeLookup`
and `Answer`. Keep A2A serving, identity, budgets, tasks, and approvals in the
application. A model implements the domain lookup port; it cannot create grants,
select credentials, change destinations, or turn an answer into a business action.

## Runtime and hardware choice

| Situation | Candidate | What to verify before adoption |
| --- | --- | --- |
| Apple Silicon teaching machine | Native Ollama with a reviewed small instruction model | Runtime version, local-only configuration, RAM headroom, cold/warm latency and cancellation behavior. |
| Explicit GGUF artifact and inference flags | Native `llama-server` from llama.cpp | Pinned runtime release/commit, artifact hash, license, tokenizer/chat template, context and output limits. |
| Linux NVIDIA workstation | Reviewed runtime with supported GPU/container setup | Driver/toolkit compatibility, memory budget, network isolation and queue bounds. |

Ollama documents that macOS Docker Desktop lacks GPU acceleration for its Docker
container. For this Mac, evaluate native inference separately from the existing
containerized A2A lab. Do not infer GPU behavior for every Docker product from this
specific limitation. [Ollama FAQ](https://docs.ollama.com/faq)

Start an evaluation with one small quantized instruction model and short synthetic
contexts. Approximate raw weight storage is `parameters × bits / 8`: 3 billion
parameters at 4 bits is about 1.5 GB before metadata, runtime buffers and KV cache.
This arithmetic is not a RAM requirement or quality recommendation. Measure peak
memory and reserve headroom for macOS, Docker and concurrent work. Longer contexts
and concurrent inference increase resource use; size limits must be measured.

## Acquire a reviewed artifact

Record runtime version, model repository, immutable revision/digest, filename,
quantization, license, source hash, chat template and download date. Review model
documentation and avoid enabling remote repository code merely to load weights.
Model availability and terms change; select the actual artifact during the later
integration milestone rather than freezing an untested recommendation here.

For an approved Hugging Face GGUF artifact, the official CLI supports revision
selection. Replace the placeholders and install the reviewed CLI separately from
the lab's locked environment:

```sh
hf download APPROVED_REPO APPROVED_FILE.gguf --revision IMMUTABLE_COMMIT --local-dir /approved/models
shasum -a 256 /approved/models/APPROVED_FILE.gguf
```

The local checksum records bytes obtained; it does not establish publisher trust
unless compared to independently trusted provenance.
[Hugging Face CLI](https://huggingface.co/docs/huggingface_hub/guides/cli)

## Optional Ollama smoke check

Install a reviewed Ollama release through its official distribution. For a
manually started server, use explicit loopback and local-only settings. If the
desktop app already serves that port, quit it or configure that instance using
the platform-specific FAQ rather than starting a competing server.

```sh
OLLAMA_NO_CLOUD=1 OLLAMA_HOST=127.0.0.1:11434 ollama serve
# In another terminal, after choosing the reviewed tag:
ollama pull APPROVED_LOCAL_MODEL_TAG
ollama list
ollama --version
```

Ollama's local API requires no authentication. Bind it to loopback; treat local
processes and administrators as within its trust boundary. Its FAQ documents
`OLLAMA_NO_CLOUD=1` and local binding. Record the resolved local model ID and
provenance; a mutable tag alone is not an immutable model baseline.
[Authentication](https://docs.ollama.com/api/authentication),
[configuration FAQ](https://docs.ollama.com/faq)

Use synthetic data for a direct runtime check, substituting the same reviewed tag:

```sh
curl --fail --max-time 30 http://127.0.0.1:11434/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"model":"APPROVED_LOCAL_MODEL_TAG","prompt":"Return JSON with answer containing one runbook tip and references as an empty array.","format":"json","stream":false,"options":{"num_ctx":2048,"num_predict":128}}'
ollama ps
```

The response is a runtime envelope; parse its `response` field as JSON and then
validate the domain `Answer`. JSON formatting is not permission or semantic
correctness. This smoke check does not exercise A2A, and its timeout does not prove
the inference server stopped work. [Generate API](https://docs.ollama.com/api/generate),
[generation parameters](https://docs.ollama.com/modelfile#valid-parameters-and-values)

As an alternative, a reviewed llama.cpp build serves an approved local GGUF using
explicit endpoint/context flags:

```sh
llama-server -m /approved/models/APPROVED_FILE.gguf --host 127.0.0.1 --port 8081 -c 2048 -n 128
```

Check the installed release's help and pin it before implementation. The upstream
server documentation is moving; do not adopt its default port or extra tools as
lab permissions. [llama.cpp server](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

## Adapter and network work still required

1. Add a provider implementing `KnowledgeLookup.answer`, with validated startup
   configuration and an exact separately approved inference endpoint. The current
   A2A URL allowlist is for peers, not a generic HTTP tool permission.
2. Use HTTPX with explicit deadlines, bounded response bytes, no redirects/proxies,
   finite queue/concurrency and output-token limits. Parse the runtime envelope,
   validate `Answer`, and reject malformed, oversized or unexpected content.
3. Pass only authorized source text to inference. Resolve citations from source
   identifiers controlled by the application; model-invented references are not
   provenance. Keep secrets, grants, private policies and other users' tasks out.
4. Preserve cancellation propagation and prevention of late task artifacts. Test
   remote inference continuing after a client timeout; do not promise GPU work
   termination without runtime evidence.
5. Keep fixture mode for reproducible teaching and tests. Add opt-in integration
   checks for quality, adversarial prompts, malformed output, cold/warm latency,
   peak memory, concurrency, cancellation and model/runtime upgrades.

The current Compose internal network cannot reach a host inference service, and
container loopback is not host loopback. Connecting native Mac inference requires
an explicit network design (for example a restricted gateway), destination policy
and separate authentication review. Do not fix this by broadly binding a model to
`0.0.0.0`, publishing the lab ports, or removing the internal network. A first
model adapter can instead be evaluated in the native loopback setup once its
environment is reliably resident. No connectivity change is included in M5.

An integration completion record must identify exact runtime/model artifacts,
measured machine specifications, observed budgets, failure outcomes and residual
risks. Claims about prompt resistance require model-specific evaluations in
addition to deterministic application-policy tests.
