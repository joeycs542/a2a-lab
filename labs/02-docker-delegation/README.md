# Lab 2: Docker A2A delegation

Run this lab from the code repository with Docker Desktop and Docker Compose.
It uses the same Python 3.12.13, pinned SDK, deterministic workflows, Agent Cards,
task lifecycle, and approval policy as the host lab. No models are downloaded.

## Start the authenticated lab

```sh
docker compose up --build -d --wait
docker compose run --rm client call --text "What belongs in a runbook?"
docker compose logs coordinator knowledge
```

The first build downloads Python/uv images and locked dependencies. Host `.venv`,
`.env`, Git metadata, runtime credentials, and caches are excluded from the build
context. The installed application is a normal wheel inside the image, with no
source bind mounts. An iCloud-hosted checkout needs its source files downloaded
for the initial build; container execution uses Docker-managed files afterward.

The initializer creates one-hour teaching credentials in separate operator,
coordinator, and knowledge Docker volumes. It reuses valid existing credentials
and refuses incomplete, mismatched, or expired sets without overwriting them.
Knowledge mounts only its verifier file; coordinator mounts its verifiers and
scoped service tokens; the client mounts user and separate human-control tokens.
Values are never printed. Host `.runtime/security` is not used.

Knowledge and coordinator are independent containers with separate process and
filesystem namespaces. They share a loopback network namespace owned by the
knowledge container: `127.0.0.1:8101` is coordinator and `127.0.0.1:8102` is
knowledge. This preserves existing endpoint and loopback policies without adding
general network bind addresses. There are no published host ports. The outer
Docker bridge is internal; the runtime does not require Internet access.

Health checks fetch each public card on loopback. Coordinator waits for healthy
knowledge, and client commands wait for healthy coordinator. Startup errors are
visible in `docker compose logs`; a failed credential initializer prevents agent
startup. Inspect status with `docker compose ps -a`.

## Exercise discovery and ownership

```sh
docker compose run --rm client call --agent knowledge --text "What should an Agent Card describe?"
docker compose run --rm client call --async --text "What belongs in a runbook?"
docker compose run --rm client task list
docker compose run --rm client task get TASK_ID
docker compose run --rm client task get TASK_ID --as bob
```

Replace `TASK_ID` with Alice's returned task ID. Alice can read it; Bob is denied.
`[fail]` still produces a controlled failed task. `[slow]` uses the default
two-second delay, so manual cancellation needs to occur before it completes.
Use the existing [Lab 3](../03-secure-delegation/README.md) to understand the
approval and lifecycle invariants.

For the full human-control exercise, enter the operator container:

```sh
docker compose run --rm --entrypoint /bin/sh client
```

Inside that shell, run the Lab 3 `a2a-lab` commands directly, omitting `uv run` and
the host server/setup commands. Write proposal and approval files under `/work`,
which is a Docker volume retained across client invocations. The profile and
credential path are already configured. `--confirm` remains an explicit operator
action; A2A messages do not acquire human approval permission.

The non-root containers have read-only root filesystems, no Linux capabilities,
no privilege escalation, and bounded memory, CPU, process count, and temporary
storage. This is a local teaching deployment: the operator can simulate every
account and control Docker. Sharing a network namespace does not provide network
isolation between agents, TLS, signed cards, or cryptographic server identity.

## Optional unauthenticated profile

Stop the current containers, retaining their teaching volumes, then use the override:

```sh
docker compose down
docker compose -f compose.yaml -f compose.demo.yaml up --build -d --wait
docker compose -f compose.yaml -f compose.demo.yaml run --rm client call
```

The override changes only the authentication profile. Ports remain unpublished
and endpoint, payload, deadline, and workflow limits still apply. Approval HTTP
routes are unavailable in this profile. Use the same file selection for teardown;
restart with the default Compose file to return to authenticated behavior.

## Rebuild, expiry, and teardown

After code changes, rerun `docker compose up --build -d --wait`. Replacing an agent
loses its in-memory tasks and approval records. Recreating knowledge also requires
coordinator recreation because it owns their shared network namespace; Compose's
dependency restart setting handles an explicit dependency update. The lab does
not promise durable recovery or automatic healing of a failed peer.

```sh
docker compose down
```

This stops the lab while retaining teaching credentials and `/work`. Credentials
expire after one hour, including while containers are stopped. To reset an expired
or partial setup for a new lab session:

```sh
docker compose --profile tools down --volumes
docker compose up --build -d --wait
```

The reset deletes this Compose project's credential volumes **and saved `/work`
proposal/approval files**. It does not delete repository files or host credentials.
It is deliberate reset of synthetic lab state, not silent credential renewal.
Selecting `tools` includes the client-only `/work` volume in teardown; without
that profile, Compose may retain it even when `--volumes` is specified.

## Verify the image

```sh
docker build --target verify -t a2a-lab:verify .
```

The verification stage installs locked development dependencies and runs Ruff
lint/format, strict mypy, and the complete behavioral suite inside Linux. The
check command runs without external networking; loopback remains available for
integration tests. Image/package installation occurs before that command. The
runtime image contains runtime dependencies only. The
container decision (private decision record) records verified
behavior and design limits.
