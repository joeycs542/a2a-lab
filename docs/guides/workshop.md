# A2A workshop facilitator runbook

Duration: 90 minutes. Audience: engineers familiar with HTTP and Python.
Use synthetic engineering notes and the authenticated Docker profile. Models,
API keys, Django, and MCP servers are not required. Prepare Docker Desktop and
the image before the session; image downloads are separate from demo latency.

## Agenda and preparation

| Minutes | Activity | Observable learning outcome |
| --- | --- | --- |
| 0–10 | Explain domain, A2A, and policy boundaries | Identify where authority is checked. |
| 10–25 | Inspect cards and delegate | Explain configured discovery and the live HTTP trace. |
| 25–40 | Read, deny, and cancel a task | Distinguish task identifiers from ownership. |
| 40–60 | Propose, review, approve, execute and retry | Distinguish proposals, grants, and receipts. |
| 60–75 | Review OWASP evidence and gaps | Name an enforcement point and a residual risk. |
| 75–90 | Explore cards/extension and local model design | Keep provider changes outside authorization. |

Run commands from the code repository. Use the named `a2a-workshop` project below
for every host command so it does not reuse your normal demo volumes. The
override gives `[slow]` a 15-second delay, a 30-second workflow limit, and a
600-poll cap. It changes only this workshop invocation. Credentials expire after
one hour by default. Prebuild the image beforehand, but create the fresh project
at minute 10, immediately before live exercises. Finish live calls by minute 60;
the last 30 minutes are discussion and code review. For extra live extension work,
finish/clean up this project and create a fresh one first. Plan a fresh reset
between workshop cohorts rather than extending old credentials.

```sh
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml up --build -d --wait
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml run --rm client doctor
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml run --rm client call
```

Expected: Python 3.12.13 and SDK 1.2.2; live card discovery, a coordinator call,
and a composed answer with a `task_id`. Server logs show coordinator-to-knowledge
delegation. No host ports are exposed. [Lab 2](../../labs/02-docker-delegation/README.md)
explains container/network/credential boundaries and normal teardown.

Open an operator shell. Keep it open through the exercises:

```sh
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml run --rm --entrypoint /bin/sh client
```

All commands in the next sections run **inside that shell**, without `uv` or a
`docker compose` prefix. Its working directory is `/work`, a private teaching
volume. Proposal files contain synthetic data. The operator holds all simulated
user/human credentials; explain this limitation before the approval exercise.

## 1 Inspect discovery and contracts

```sh
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8102/.well-known/agent-card.json', timeout=2).read().decode())"
a2a-lab call --text "What should an Agent Card describe?"
```

Find the knowledge capability, JSON-RPC interface, protocol version, text input,
JSON output, and bearer declaration. No credential value appears in the card.
There is one approved candidate from configuration. The well-known path retrieves
metadata for that candidate; it does not search the network. The client checks
compatibility and exact endpoints before sending work.

Use [Lab 5](../../labs/05-agent-cards/README.md) for incompatible-card checks and
the pinned SDK skill. Discuss: an advertised capability cannot create authority,
and a valid card alone cannot authenticate the server.

## 2 Observe ownership and cancellation

```sh
a2a-lab call --async --text "[slow] What belongs in a runbook?"
```

Copy the returned `id` into `TASK_ID` below. This is a placeholder, not a literal
task name. Run promptly, before the 15-second fixture finishes:

```sh
a2a-lab task get TASK_ID
a2a-lab task get TASK_ID --as bob
a2a-lab task cancel TASK_ID --as bob
a2a-lab task cancel TASK_ID
a2a-lab task get TASK_ID
a2a-lab task list --as bob
```

Alice can retrieve and cancel her task. Bob's get/cancel commands exit nonzero
with a denial; his list excludes Alice's task. Alice's successful cancellation
returns `TASK_STATE_CANCELED`. Wait beyond the fixture delay, then retrieve it
again: it remains canceled without an answer artifact. If completion wins the
race, start a fresh slow task and cancel sooner. Do not call that race a defect.

```sh
a2a-lab call --text "[fail] runbook"
```

Expected: nonzero controlled failure. Retrieve the new ID from Alice's task list
to inspect its failed state. A timeout or unacknowledged cancellation can leave a
remote outcome unknown; see [Lab 3](../../labs/03-secure-delegation/README.md) for
the host timeout exercise and [security limits](../security.md).

## 3 Review and authorize exact terms

```sh
a2a-lab call --text "What belongs in a runbook?"
a2a-lab task get TASK_ID
```

Use this **new completed task's** ID and `artifacts[0].artifactId`, replacing both
placeholders. A canceled or failed task is not a proposal source.

```sh
a2a-lab action propose --task-id TASK_ID --artifact-id ARTIFACT_ID --label "Reviewed engineering note" > proposal.json
cat proposal.json
```

Review the artifact and proposal. Check owner scope, operation, destination,
resource IDs, label, revision, and content snapshot digest. The destination is
`local-display`; this creates a receipt only. It has no purchasing or publishing
effect. After the human review, approve and execute promptly:

```sh
a2a-lab action approve --proposal-file proposal.json --confirm > approval.json
a2a-lab action execute --proposal-file proposal.json --approval-file approval.json --idempotency-key workshop-note-1
a2a-lab action execute --proposal-file proposal.json --approval-file approval.json --idempotency-key workshop-note-1
a2a-lab action execute --proposal-file proposal.json --approval-file approval.json --idempotency-key workshop-note-2
```

The first two executions return the same `release_id`; the new key is denied.
Default grant expiry is 60 seconds. An exact retry returns its confirmed receipt
after grant expiry, provided the caller credential is valid. Creating another
grant for this already released proposal cannot produce a second release.

Prepare a **second unreleased proposal** using the same completed artifact.
Approve it, then change its label in a separate file:

```sh
a2a-lab action propose --task-id TASK_ID --artifact-id ARTIFACT_ID --label "Second reviewed note" > second.json
a2a-lab action approve --proposal-file second.json --confirm > second-approval.json
python -c "import json; p=json.load(open('second.json')); p['terms']['label']='Changed after approval'; json.dump(p,open('changed.json','w'))"
a2a-lab action execute --proposal-file changed.json --approval-file second-approval.json --idempotency-key changed-note-1
a2a-lab action approve --proposal-file second.json --confirm --as bob
```

Both attempts are denied. The first changes approved terms; the second uses a
human identity for a different owner. A model-generated `approved: true` cannot
create a grant. Automated tests cover expiry, wrong roles, content changes and
concurrent attempts; they simulate approvers rather than prove real human review.

## 4 Debrief and cleanup

Ask participants to trace each decision to [security evidence](../security.md):
card validation, recipient identity, ownership, output bounds, cancellation,
exact approval, and replay handling. Then ask what a remote production deployment
would still need: TLS/server identity, central identity/revocation, protected human
review, durable transactional state, per-tenant quotas, monitoring and recovery.

The [extension](../../labs/04-boilerplate-extension/README.md) and
[model integration guide](local-model-integration.md) explain later work. Current
fixtures do not assess LLM persuasion, answer quality, or model hardware latency.

Exit the operator shell. On the host, inspect safe logs and remove only this
temporary project's containers and teaching volumes:

```sh
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml logs coordinator knowledge
docker compose -p a2a-workshop -f compose.yaml -f compose.workshop.yaml --profile tools down --volumes
```

This deletes workshop credentials and saved proposal files. The `tools` profile
includes the operator-work volume in cleanup. Normal `down` without `--volumes`
preserves volumes. Restart loses server task/approval state even when volumes
remain. Expired or partial credentials fail closed; deliberate fresh-volume reset
is the teaching recovery procedure.
