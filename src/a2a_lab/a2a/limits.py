"""Bound inbound bodies and outbound requests before SDK deserialization."""

import asyncio

import httpx
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from a2a_lab.config import Settings


class BoundaryError(ValueError):
    """A request or response violated the configured peer boundary."""


class BoundedTransport(httpx.AsyncBaseTransport):
    """Permit exact configured URLs and cap decoded response bytes."""

    def __init__(
        self,
        urls: frozenset[str],
        max_bytes: int,
        inner: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._urls = urls
        self._max_bytes = max_bytes
        self._inner = inner or httpx.AsyncHTTPTransport(retries=0, trust_env=False)

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if str(request.url) not in self._urls:
            raise BoundaryError("Outbound destination is not approved.")
        if len(request.content) > self._max_bytes:
            raise BoundaryError("Outbound payload exceeds the byte limit.")
        response = await self._inner.handle_async_request(request)
        try:
            # Refuse compression so decompression cannot allocate an unbounded chunk.
            if response.headers.get("content-encoding", "identity") != "identity":
                raise BoundaryError("Compressed peer responses are unsupported.")
            length = response.headers.get("content-length")
            if length is not None and (not length.isdecimal() or int(length) > self._max_bytes):
                raise BoundaryError("Peer response exceeds the byte limit.")
            content = bytearray()
            if response.is_stream_consumed:
                if len(response.content) > self._max_bytes:
                    raise BoundaryError("Peer response exceeds the byte limit.")
                content.extend(response.content)
            else:
                async for chunk in response.aiter_raw():
                    if len(content) + len(chunk) > self._max_bytes:
                        raise BoundaryError("Peer response exceeds the byte limit.")
                    content.extend(chunk)
            return httpx.Response(
                response.status_code,
                headers=response.headers,
                content=bytes(content),
                request=request,
                extensions=response.extensions,
            )
        finally:
            await response.aclose()

    async def aclose(self) -> None:
        await self._inner.aclose()


class RequestLimits:
    """Cap active HTTP requests and buffer only bounded request bodies."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self._app = app
        self._settings = settings
        self._active = 0

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        if self._active >= self._settings.max_concurrent_requests:
            await PlainTextResponse("Request capacity reached.", status_code=503)(
                scope, receive, send
            )
            return
        self._active += 1
        try:
            body = bytearray()
            try:
                async with asyncio.timeout(self._settings.request_timeout_seconds):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > self._settings.max_payload_bytes:
                            await PlainTextResponse("Payload exceeds byte limit.", status_code=413)(
                                scope, receive, send
                            )
                            return
                        body.extend(chunk)
                        if not message.get("more_body", False):
                            break
            except TimeoutError:
                await PlainTextResponse("Request body deadline exceeded.", status_code=408)(
                    scope, receive, send
                )
                return

            delivered = False

            async def bounded_receive() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            await self._app(scope, bounded_receive, send)
        finally:
            self._active -= 1
