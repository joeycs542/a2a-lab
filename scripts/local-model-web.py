"""Run the native model-backed browser demo and stop owned agents on exit."""

import asyncio
import signal
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn

from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.security.identity import initialize_security
from a2a_lab.web.server import create_web_app


class BrowserServer(uvicorn.Server):
    """Let the supervisor reap children before returning control to the shell."""

    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # Uvicorn's signal replay would cancel the supervisor during child cleanup.
        previous = {
            sig: signal.signal(sig, self.handle_exit) for sig in (signal.SIGINT, signal.SIGTERM)
        }
        try:
            yield
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


async def main() -> None:
    """Use fresh, temporary credentials without modifying another demo."""
    with TemporaryDirectory(prefix="a2a-model-") as directory:
        credentials = Path(directory) / "credentials"
        initialize_security(credentials, 3600, topology="discovery")
        settings = Settings(
            profile="local-secure",
            topology="discovery",
            discovery_mode="review",
            inference_backend="ollama",
            request_timeout_seconds=120,
            max_task_polls=1000,
            credentials_directory=credentials,
        )
        async with running_agents(settings, print):
            server = BrowserServer(
                uvicorn.Config(create_web_app(settings), host=settings.host, port=settings.web_port)
            )
            await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
