# Lab 3 Authenticated lifecycle and human approval

Learn how verified identity controls tasks and how a separate human approval
authorizes one exact synthetic commitment. The two Python agents still use
bundled notes, with no model or paid API. Follow the repository [setup](../../README.md)
and its non-editable installation fallback when needed.

For Docker, follow the [workshop runbook](../../docs/guides/workshop.md). It provides
the complete task/approval exercise inside an operator container, a named project,
and an optional bounded timing override for manual cancellation. The host commands
below remain available for a reliably installed native environment.

## Generate credentials and run the profile

From the code repository, once per fresh private credential directory:

```sh
uv run a2a-lab init-security
uv run a2a-lab demo --secure
```

The files under `.runtime/security` are ignored by Git. Values are not printed.
They expire after one hour by default; existing files are never overwritten.
For a fresh directory, use `init-security --directory .runtime/security-new`,
set `A2A_LAB_CREDENTIALS_DIRECTORY` to its absolute path in every terminal,
and restart servers. The CLI operator holds the synthetic Alice/Bob user
identities and separate human-control credentials. This is a teaching issuer,
not an external login service or proof of a physical human's identity.

## Observe task ownership and cancellation

Use separate terminals with the same profile and credential-directory setting:

For this manual cancellation exercise, first set these values in every terminal
to allow time to inspect a running task. They do not change the normal defaults:

```sh
export A2A_LAB_REQUEST_TIMEOUT_SECONDS=30
export A2A_LAB_FIXTURE_DELAY_SECONDS=15
export A2A_LAB_MAX_TASK_POLLS=600
```

```sh
# Terminal 1
export A2A_LAB_PROFILE=local-secure
uv run a2a-lab serve knowledge
# Terminal 2
export A2A_LAB_PROFILE=local-secure
uv run a2a-lab serve coordinator
# Terminal 3
export A2A_LAB_PROFILE=local-secure
uv run a2a-lab call --async --text "[slow] What belongs in a runbook?"
```

Copy the task's `id` into the following commands in Terminal 3. Cancel promptly,
before the configured fixture finishes; completion can win a race.

```sh
uv run a2a-lab task get TASK_ID
uv run a2a-lab task get TASK_ID --as bob
uv run a2a-lab task cancel TASK_ID --as bob
uv run a2a-lab task cancel TASK_ID
uv run a2a-lab task get TASK_ID
uv run a2a-lab task list
```

Alice can read and cancel her task; Bob is denied and his list excludes it.
Successful cancellation returns `TASK_STATE_CANCELED`. After cancellation,
the task cannot publish a late answer artifact. The coordinator cancels its
known delegated task using its own recipient-bound credential when supported.
Invalid/expired credentials and wrong-recipient tokens are rejected before
execution. Role or owner claims in message metadata cannot change identity.

Use `[fail] runbook` for a controlled failure. To inspect a timeout, restart
the knowledge server with `A2A_LAB_FIXTURE_DELAY_SECONDS=6` and
`A2A_LAB_REQUEST_TIMEOUT_SECONDS=5`, then submit a `[slow] runbook` request.
The knowledge agent's five-second workflow limit prevents an
unbounded wait. Inspect task state rather than treating a timeout as evidence
of a particular remote outcome. Restore the normal settings afterward.

## Review and authorize one exact fixture release

In Terminal 3, complete a normal lookup and retrieve its artifact:

```sh
uv run a2a-lab call --text "What belongs in a runbook?"
uv run a2a-lab task get TASK_ID
```

Copy the returned task ID and `artifacts[0].artifactId`. Create a proposal:

```sh
uv run a2a-lab action propose --task-id TASK_ID --artifact-id ARTIFACT_ID \
  --label "Reviewed engineering note" > .runtime/proposal.json
```

Review the artifact content and proposal file. Check the acting scope, task,
artifact, operation, destination, label, revision, and content digest. The
only destination is `local-display`; execution records a local JSON receipt.
It does not buy components, pay money, publish a file, or send a message.

As the human operator, explicitly approve the exact reviewed proposal:

```sh
uv run a2a-lab action approve --proposal-file .runtime/proposal.json \
  --confirm > .runtime/approval.json
uv run a2a-lab action execute --proposal-file .runtime/proposal.json \
  --approval-file .runtime/approval.json --idempotency-key reviewed-note-1
```

Approval uses the separate human-control credential. A user or service
credential cannot mint approval, and an `approved: true` payload is rejected.
The approval binds the actor/resource/terms/revision/content snapshot and
expires after 60 seconds by default. The executor checks current artifact
content and consumes authority atomically with its receipt.

Repeat the exact execute command with the same idempotency key: it returns
the same `release_id`. A different key cannot replay that approval. Editing
the label or revision after approval is denied. Creating multiple grants for
one proposal still cannot commit it twice. A completed A2A task is knowledge
output, not a business approval.

Stop both manually served agents with Ctrl+C. Restart removes tasks, proposals,
approvals, and receipts; old identifiers cannot recover or replay that state.

## Verify and discuss the boundaries

```sh
uv run pytest tests/security tests/integration/test_secure_delegation.py
```

Tests automate synthetic human-role requests to verify enforcement; they do
not claim a real person reviewed an artifact. They also check cooperative
shutdown, late-result prevention, credential disclosure, finite polling,
retained-record limits, default-denied routes, and shared-key concurrency.

Use the M3 decision (private decision record)
and [constitution](../../docs/constitution.md) to discuss OWASP least privilege,
untrusted input, bounded work, and action integrity. The operator owns all test
credentials and the processes share an OS account. This profile authenticates
callers but does not provide TLS, signed server identity, OS isolation, durable
recovery, or model prompt-injection evaluation. Remote start/cancel responses
can be lost; uncertainty must stay visible instead of triggering a blind retry.
