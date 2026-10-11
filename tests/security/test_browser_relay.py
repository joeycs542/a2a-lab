import httpx

from a2a_lab.web.relay import create_relay_app


async def test_relay_keeps_destination_fixed_and_preserves_browser_protections() -> None:
    requests: list[httpx.Request] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            headers={"Set-Cookie": "a2a_session=private; HttpOnly; SameSite=Strict"},
            text="Gateway response",
        )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(create_relay_app(httpx.MockTransport(upstream))),
        base_url="http://127.0.0.1:8080",
    ) as client:
        page = await client.get("/")
        assert "HttpOnly" in page.headers["set-cookie"]
        await client.post(
            "/api/ask",
            json={"text": "release"},
            headers=[
                ("Origin", "http://127.0.0.1:8080"),
                ("Origin", "http://forged"),
                ("X-Lab-CSRF", "nonce"),
                ("Authorization", "must-not-be-forwarded"),
            ],
        )
        assert requests[-1].headers.get_list("origin") == [
            "http://127.0.0.1:8080",
            "http://forged",
        ]
        assert requests[-1].headers["host"] == "127.0.0.1:8080"
        assert "authorization" not in requests[-1].headers
        count = len(requests)
        assert (await client.get("/api/task?id=abc&url=http://forged")).status_code == 400
        assert (await client.get("/a2a/jsonrpc")).status_code == 404
        assert len(requests) == count
        await client.get("/api/task?id=abc")
        assert str(requests[-1].url) == "http://knowledge:8080/api/task?id=abc"
        assert all(request.url.host == "knowledge" for request in requests)


async def test_relay_refuses_unbounded_response_and_does_not_follow_redirects() -> None:
    requests: list[httpx.Request] = []

    async def upstream(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/style.css":
            return httpx.Response(200, content=b"x" * 65537)
        return httpx.Response(302, headers={"Location": "http://forged"})

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(create_relay_app(httpx.MockTransport(upstream))),
        base_url="http://127.0.0.1:8080",
    ) as client:
        assert (await client.get("/style.css")).status_code == 503
        assert (await client.get("/")).status_code == 503
        assert len(requests) == 2
