"""Exercise model mode over real HTTP with a controlled Ollama-compatible server."""

import asyncio
import json
import socket
import threading
from contextlib import ExitStack
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from a2a_lab.a2a.client import PeerClient
from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.domain.roles import services_for
from a2a_lab.security.identity import initialize_security


async def test_model_review_uses_real_a2a_handoffs(tmp_path: Path) -> None:
    requests: list[dict[str, object]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            assert self.path == "/api/chat"
            assert not self.headers.get("Authorization")
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            response = json.dumps(
                {"done": True, "message": {"content": "## Generated specialist finding"}}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, format: str, *args: object) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as model:
        thread = threading.Thread(target=model.serve_forever, daemon=True)
        thread.start()
        try:
            credentials = tmp_path / "keys"
            initialize_security(credentials, topology="discovery")
            ports = {}
            with ExitStack() as stack:
                for service in services_for("discovery"):
                    listener = stack.enter_context(socket.socket())
                    listener.bind(("127.0.0.1", 0))
                    ports[f"{service}_port"] = listener.getsockname()[1]
            settings = Settings(
                _env_file=None,
                profile="local-secure",
                topology="discovery",
                discovery_mode="review",
                inference_backend="ollama",
                ollama_port=model.server_port,
                credentials_directory=credentials,
                request_timeout_seconds=20,
                **ports,
            )
            events: list[str] = []
            async with running_agents(settings, events.append):
                result = await PeerClient(settings, "coordinator", events.append).call(
                    "Review runbook, security and release readiness."
                )
            assert len(requests) == 3
            assert result.answer.answer.count("Generated specialist finding") == 3
            assert len(result.answer.references) == 3
            assert any("rpc.send agent=runbook" in event for event in events)
        finally:
            await asyncio.to_thread(model.shutdown)
            thread.join(timeout=2)
