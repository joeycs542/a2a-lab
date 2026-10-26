import asyncio

import httpx
import pytest
from starlette.responses import PlainTextResponse

from a2a_lab.a2a.limits import BoundaryError, BoundedTransport, RequestLimits
from a2a_lab.config import Settings


async def test_unapproved_url_is_rejected_without_touching_transport() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        pytest.fail("Unapproved destination reached the network transport")

    async with (
        httpx.AsyncClient(
            transport=BoundedTransport(
                frozenset({"http://127.0.0.1:8102/approved"}), 1024, httpx.MockTransport(respond)
            )
        ) as client,
    ):
        with pytest.raises(BoundaryError):
            await client.get("http://169.254.169.254/")


@pytest.mark.parametrize("headers", [{}, {"content-length": "5000"}])
async def test_oversized_peer_response_is_rejected(headers: dict[str, str]) -> None:
    transport = BoundedTransport(
        frozenset({"http://127.0.0.1:8102/card"}),
        1024,
        httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"x" * 5000, headers=headers)
        ),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BoundaryError):
            await client.get("http://127.0.0.1:8102/card")


async def test_chunked_request_size_and_capacity_are_bounded() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    async def app(scope, receive, send):
        entered.set()
        await release.wait()
        await PlainTextResponse("ok")(scope, receive, send)

    limits = RequestLimits(
        app, Settings(_env_file=None, max_payload_bytes=1024, max_concurrent_requests=1)
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=limits), base_url="http://lab"
    ) as client:
        first = asyncio.create_task(client.post("/", content="valid"))
        await asyncio.wait_for(entered.wait(), 1)
        try:
            second = await client.post("/", content="valid")
            assert second.status_code == 503
        finally:
            release.set()
            assert (await first).status_code == 200

        async def chunks():
            yield b"x" * 600
            yield b"x" * 600

        oversized = await client.post("/", content=chunks())
        assert oversized.status_code == 413
        assert (await client.post("/", content="valid")).status_code == 200


async def test_slow_request_body_hits_a_deadline_and_releases_capacity() -> None:
    async def app(scope, receive, send):
        await PlainTextResponse("ok")(scope, receive, send)

    limits = RequestLimits(app, Settings(_env_file=None, request_timeout_seconds=0.02))

    async def slow_body():
        yield b"partial"
        await asyncio.sleep(10)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=limits), base_url="http://lab"
    ) as client:
        response = await client.post("/", content=slow_body())
        assert response.status_code == 408
        assert (await client.post("/", content="valid")).status_code == 200


async def test_streamed_peer_body_is_capped_and_closed_without_content_length() -> None:
    closed = False

    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"x" * 600
            yield b"x" * 600

        async def aclose(self) -> None:
            nonlocal closed
            closed = True

    transport = BoundedTransport(
        frozenset({"http://127.0.0.1:8102/card"}),
        1024,
        httpx.MockTransport(lambda request: httpx.Response(200, stream=Body())),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BoundaryError, match="byte limit"):
            await client.get("http://127.0.0.1:8102/card")
    assert closed


async def test_compressed_peer_response_is_rejected_before_decompression() -> None:
    transport = BoundedTransport(
        frozenset({"http://127.0.0.1:8102/card"}),
        1024,
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={"content-encoding": "gzip"}, stream=httpx.ByteStream(b"compressed")
            )
        ),
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BoundaryError, match="Compressed"):
            await client.get("http://127.0.0.1:8102/card")


async def test_oversized_outbound_body_never_reaches_peer() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        pytest.fail("Oversized request reached the peer")

    transport = BoundedTransport(
        frozenset({"http://127.0.0.1:8102/rpc"}), 1024, httpx.MockTransport(respond)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BoundaryError, match="Outbound payload"):
            await client.post("http://127.0.0.1:8102/rpc", content=b"x" * 1200)
