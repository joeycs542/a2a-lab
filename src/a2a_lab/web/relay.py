"""Credential-free ingress between the host loopback port and private gateway."""

import asyncio
from urllib.parse import urlencode

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from a2a_lab.a2a.limits import BoundedTransport, RequestLimits
from a2a_lab.config import Settings

UPSTREAM = "http://knowledge:8080"
FORWARD_HEADERS = frozenset({"host", "origin", "content-type", "cookie", "x-lab-csrf"})
HOP_HEADERS = frozenset({"connection", "transfer-encoding", "keep-alive"})


def create_relay_app(transport: httpx.AsyncBaseTransport | None = None) -> Starlette:
    """Forward only browser routes to one fixed gateway, with no credentials or retries."""
    settings = Settings()

    async def forward(request: Request) -> Response:
        query = ""
        if request.url.query:
            params = request.query_params.multi_items()
            if (
                request.url.path != "/api/task"
                or len(params) != 1
                or params[0][0] != "id"
                or not 1 <= len(params[0][1]) <= 128
            ):
                return JSONResponse({"error": "Invalid browser query."}, status_code=400)
            query = "?" + urlencode(params)
        url = UPSTREAM + request.url.path + query
        headers = [(key, value) for key, value in request.headers.items() if key in FORWARD_HEADERS]
        headers.append(("accept-encoding", "identity"))
        try:
            async with (
                asyncio.timeout(15),
                httpx.AsyncClient(
                    transport=BoundedTransport(frozenset({url}), 65536, transport),
                    timeout=10,
                    trust_env=False,
                    follow_redirects=False,
                ) as client,
            ):
                upstream = await client.request(
                    request.method, url, headers=headers, content=await request.body()
                )
                if upstream.is_redirect:
                    raise ValueError("Gateway redirects are unsupported.")
                response = Response(upstream.content, status_code=upstream.status_code)
                response.raw_headers = [
                    (key, value)
                    for key, value in upstream.headers.raw
                    if key.decode("ascii").lower() not in HOP_HEADERS
                ]
                return response
        except (httpx.HTTPError, ValueError, TimeoutError):
            return JSONResponse(
                {"error": "Gateway unavailable. A lost start reply may leave an unknown outcome."},
                status_code=503,
            )

    return Starlette(
        routes=[
            Route(path, forward, methods=[method])
            for method, paths in {
                "GET": ("/", "/app.js", "/style.css", "/api/session", "/api/task"),
                "POST": ("/api/ask", "/api/identity", "/api/cancel"),
            }.items()
            for path in paths
        ],
        middleware=[Middleware(RequestLimits, settings=settings)],
    )


if __name__ == "__main__":
    uvicorn.run(create_relay_app(), host="0.0.0.0", port=8080, access_log=False)
