# a2a-lab

A local Python lab demonstrating Agent2Agent (A2A) discovery, delegation,
owner-scoped tasks and cancellation. The agents use bundled synthetic fixtures;
no model download or API key is required.

## Browser demo

With Docker Desktop running, start a fresh named Compose project:

```sh
docker compose -p a2a-demo -f compose.yaml -f compose.discovery.yaml -f compose.web.yaml up --build -d --wait
```

Open http://127.0.0.1:8080/ using that exact address. Ask about runbooks,
security or release preparation. The browser displays the coordinator result and
its discovery/delegation events.

Alice and Bob are synthetic identities. Security guidance is Alice-only; Bob's
three-specialist review returns an incomplete result. The browser never receives
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
