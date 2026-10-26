"""Bounded synthetic browser sessions around the existing authenticated A2A client."""

import secrets
import time
from dataclasses import dataclass, field
from importlib.resources import files
from urllib.parse import urlsplit

import httpx
from a2a.types import TaskState
from pydantic import BaseModel, ConfigDict, Field
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a_lab.a2a.client import TERMINAL, LookupFailure, PeerClient, read_answer
from a2a_lab.a2a.limits import BoundedTransport, RequestLimits
from a2a_lab.config import Settings
from a2a_lab.security.identity import Owner, SecurityError, load_client_keys


class Question(BaseModel):
    """The browser cannot choose tokens, owners, destinations or tools."""

    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1000)


class IdentityChoice(BaseModel):
    """A labeled operator simulation, not production login."""

    model_config = ConfigDict(extra="forbid")
    owner: Owner


class TaskChoice(BaseModel):
    """Only task identifiers already assigned to this session are accepted."""

    model_config = ConfigDict(extra="forbid")
    task_id: str = Field(min_length=1, max_length=128)


@dataclass
class Session:
    owner: Owner = "alice"
    csrf: str = field(default_factory=lambda: secrets.token_urlsafe(32))
    expires: float = field(default_factory=lambda: time.monotonic() + 1800)
    tasks: dict[str, bool] = field(default_factory=dict)


def create_web_app(settings: Settings) -> Starlette:
    """Expose a loopback operator UI with private cookies and no browser bearers."""
    if settings.topology != "discovery" or settings.profile != "local-secure":
        raise SecurityError("The browser requires authenticated discovery settings.")
    # Fail before serving if the private operator configuration is unavailable.
    load_client_keys(settings.credentials_directory)
    sessions: dict[str, Session] = {}
    origin = urlsplit(settings.web_origin)

    async def endpoint(request: Request) -> Response:
        hosts = request.headers.getlist("host")
        if len(hosts) != 1 or hosts[0] != origin.netloc:
            return JSONResponse({"error": "Host not permitted."}, status_code=421)
        if request.method == "POST" and (
            request.headers.getlist("origin") != [settings.web_origin]
            or len(request.headers.getlist("content-type")) != 1
            or request.headers.get("content-type", "").split(";")[0] != "application/json"
            or len(request.headers.getlist("x-lab-csrf")) != 1
        ):
            return JSONResponse({"error": "Same-origin JSON required."}, status_code=403)
        token = request.cookies.get("a2a_session", "")
        session = sessions.get(token) if len(token) <= 64 else None
        fresh = False
        if session is not None and session.expires <= time.monotonic():
            sessions.pop(token, None)
            session = None
        path = request.url.path
        if session is None and request.method == "GET" and path in {"/", "/api/session"}:
            for expired in [
                key for key, value in sessions.items() if value.expires <= time.monotonic()
            ]:
                sessions.pop(expired, None)
            if len(sessions) >= 32:
                return JSONResponse({"error": "Session capacity reached."}, status_code=503)
            token = secrets.token_urlsafe(32)
            session = Session()
            sessions[token] = session
            fresh = True
        if request.method == "GET" and path in {"/", "/app.js", "/style.css"}:
            name = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[path]
            media = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}[path]
            response: Response = Response(
                files("a2a_lab.web").joinpath(name).read_text("utf-8"), media_type=media
            )
        elif session is None:
            response = JSONResponse({"error": "Session unavailable."}, status_code=401)
        elif request.method == "POST" and not secrets.compare_digest(
            request.headers.get("x-lab-csrf", ""), session.csrf
        ):
            response = JSONResponse({"error": "Request token required."}, status_code=403)
        else:
            try:
                response = await dispatch(request, session)
            except (ValueError, LookupFailure, SecurityError, httpx.HTTPError, TimeoutError):
                response = JSONResponse(
                    {
                        "error": (
                            "Request invalid, denied or unavailable. "
                            "A lost start reply may leave an unknown outcome."
                        )
                    },
                    status_code=400,
                )
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "connect-src 'self'; frame-ancestors 'none'; "
                    "base-uri 'none'; form-action 'self'"
                ),
            }
        )
        if fresh:
            response.set_cookie(
                "a2a_session", token, httponly=True, samesite="strict", max_age=1800
            )
        return response

    async def dispatch(request: Request, session: Session) -> Response:
        path = request.url.path
        client = PeerClient(settings, "coordinator", lambda _: None, owner=session.owner)
        if path == "/api/session":
            return JSONResponse(
                {
                    "owner": session.owner,
                    "csrf": session.csrf,
                    "tasks": list(session.tasks),
                    "identity_mode": "synthetic-operator",
                }
            )
        if path == "/api/identity":
            choice = IdentityChoice.model_validate(await request.json())
            if any(not terminal for terminal in session.tasks.values()):
                return JSONResponse(
                    {"error": "Finish or cancel active tasks before switching."}, status_code=409
                )
            session.owner = choice.owner
            session.tasks.clear()
            session.csrf = secrets.token_urlsafe(32)
            return JSONResponse({"owner": session.owner, "csrf": session.csrf})
        if path == "/api/ask":
            question = Question.model_validate(await request.json())
            if len(session.tasks) >= 16:
                return JSONResponse({"error": "Session turn limit reached."}, status_code=503)
            # No await between reserving capacity and the insertion after start: reserve first.
            reservation = "pending-" + secrets.token_hex(8)
            session.tasks[reservation] = False
            try:
                task = await client.start(question.text)
                session.tasks[task.id] = task.status.state in TERMINAL
            finally:
                session.tasks.pop(reservation, None)
            return JSONResponse({"task_id": task.id}, status_code=202)
        if path == "/api/task":
            task_id = request.query_params.get("id", "")
            if task_id not in session.tasks or task_id.startswith("pending-"):
                return JSONResponse({"error": "Task not available."}, status_code=404)
            task = await client.get_task(task_id)
            session.tasks[task_id] = task.status.state in TERMINAL
            payload: dict[str, object] = {
                "task_id": task.id,
                "state": TaskState.Name(task.status.state),
            }
            if task.status.state == TaskState.TASK_STATE_COMPLETED:
                payload["result"] = read_answer(task).answer.model_dump(mode="json")
            url = f"{settings.agent_base_url('coordinator')}/discovery/trace"
            credential = load_client_keys(settings.credentials_directory).select(
                session.owner, "coordinator"
            )
            async with httpx.AsyncClient(
                transport=BoundedTransport(frozenset({url}), settings.max_payload_bytes),
                timeout=settings.request_timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                headers={"Authorization": credential.bearer(), "Accept-Encoding": "identity"},
            ) as http:
                trace = await http.post(url, json={"task_id": task_id})
                trace.raise_for_status()
                body = trace.json()
                if (
                    not isinstance(body, dict)
                    or set(body) != {"events"}
                    or not isinstance(body["events"], list)
                    or len(body["events"]) > 64
                    or any(
                        not isinstance(event, str) or len(event) > 300 for event in body["events"]
                    )
                ):
                    raise ValueError("Invalid trace response.")
                payload["events"] = body["events"]
            return JSONResponse(payload)
        if path == "/api/cancel":
            task_choice = TaskChoice.model_validate(await request.json())
            if task_choice.task_id not in session.tasks:
                return JSONResponse({"error": "Task not available."}, status_code=404)
            task = await client.cancel_task(task_choice.task_id)
            session.tasks[task_choice.task_id] = task.status.state in TERMINAL
            return JSONResponse({"state": TaskState.Name(task.status.state)})
        return JSONResponse({"error": "Not found."}, status_code=404)

    return Starlette(
        debug=False,
        middleware=[Middleware(RequestLimits, settings=settings)],
        routes=[
            Route("/", endpoint),
            Route("/app.js", endpoint),
            Route("/style.css", endpoint),
            Route("/api/session", endpoint),
            Route("/api/task", endpoint),
            Route("/api/ask", endpoint, methods=["POST"]),
            Route("/api/identity", endpoint, methods=["POST"]),
            Route("/api/cancel", endpoint, methods=["POST"]),
        ],
    )
