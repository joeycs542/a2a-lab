"""Authenticate application routes before SDK or action execution."""

from collections.abc import Callable
from uuid import uuid4

from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from a2a_lab.config import RPC_PATH
from a2a_lab.security.identity import (
    AgentAudience,
    SecurityError,
    ServerKeys,
    current_correlation,
    current_principal,
)


class LocalAuthentication:
    """Attach only verifier-derived authority and safe correlation fields."""

    def __init__(
        self, app: ASGIApp, keys: ServerKeys, audience: AgentAudience, trace: Callable[[str], None]
    ) -> None:
        self._app = app
        self._keys = keys
        self._audience = audience
        self._trace = trace

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or (
            scope["method"] == "GET" and scope["path"] == "/.well-known/agent-card.json"
        ):
            await self._app(scope, receive, send)
            return
        correlation = str(uuid4())
        headers = [
            value.decode("latin-1")
            for key, value in scope["headers"]
            if key.lower() == b"authorization"
        ]
        try:
            if len(headers) != 1:
                raise SecurityError("Authentication failed.")
            principal = self._keys.authenticate(headers[0], self._audience)
        except SecurityError:
            self._trace(f"policy.denied request={correlation} category=authentication")
            await PlainTextResponse(
                "Authentication required.", status_code=401, headers={"WWW-Authenticate": "Bearer"}
            )(scope, receive, send)
            return
        permitted = False
        if scope["method"] == "POST":
            if scope["path"] == RPC_PATH:
                permitted = principal.role == "user" or (
                    self._audience == "knowledge" and principal.role == "service"
                )
            elif self._audience == "coordinator":
                if scope["path"] == "/control/approve":
                    permitted = principal.role == "approver"
                elif scope["path"] in {"/actions/proposals", "/actions/execute"}:
                    permitted = principal.role == "user"
        if not permitted:
            self._trace(
                f"policy.denied request={correlation} actor={principal.actor} category=operation"
            )
            await PlainTextResponse("Operation not permitted.", status_code=403)(
                scope, receive, send
            )
            return
        scope["lab_principal"] = principal
        scope["lab_correlation"] = correlation
        marker = current_principal.set(principal)
        correlation_marker = current_correlation.set(correlation)
        self._trace(
            f"policy.allowed request={correlation} actor={principal.actor} owner={principal.owner}"
        )
        try:
            await self._app(scope, receive, send)
        finally:
            current_principal.reset(marker)
            current_correlation.reset(correlation_marker)
