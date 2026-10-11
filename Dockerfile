# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.11.14@sha256:1025398289b62de8269e70c45b91ffa37c373f38118d7da036fb8bb8efc85d97 AS uv

FROM python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock .python-version README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --no-install-project
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

FROM build AS verify
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-editable
COPY tests ./tests
RUN uv run --no-sync ruff check . \
    && uv run --no-sync ruff format --check . \
    && uv run --no-sync mypy src \
    && uv run --no-sync pytest

FROM python:3.12.13-slim@sha256:229a2c5bfa27522db7815ea81f9bed70af17ccb9de9fc7ad142b1877b5830d36 AS runtime
RUN groupadd --gid 10001 lab \
    && useradd --uid 10001 --gid lab --create-home lab \
    && mkdir -p /credentials/operator /credentials/coordinator /credentials/knowledge /work \
    && chown -R lab:lab /credentials /work \
    && chmod 0700 /credentials/operator /credentials/coordinator /credentials/knowledge /work
COPY --from=build /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /work
USER 10001:10001
ENTRYPOINT ["a2a-lab"]
CMD ["doctor"]
