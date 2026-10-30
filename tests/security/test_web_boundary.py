from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from a2a_lab.config import Settings
from a2a_lab.security.identity import initialize_security, load_client_keys
from a2a_lab.web.server import create_web_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    initialize_security(tmp_path / "keys", topology="discovery")
    return Settings(
        _env_file=None,
        topology="discovery",
        profile="local-secure",
        credentials_directory=tmp_path / "keys",
    )


async def test_browser_session_csrf_origin_and_credentials_stay_private(settings: Settings) -> None:
    app = create_web_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url=settings.web_origin
    ) as client:
        page = await client.get("/")
        assert page.status_code == 200
        assert "HttpOnly" in page.headers["set-cookie"]
        assert "SameSite=strict" in page.headers["set-cookie"]
        assert "script-src 'self'" in page.headers["content-security-policy"]
        renderer = await client.get("/markdown-it.min.js")
        assert renderer.status_code == 200
        assert renderer.headers["content-type"].startswith("text/javascript")
        assert len(renderer.content) > 65536
        session = (await client.get("/api/session")).json()
        assert session["identity_mode"] == "synthetic-operator"
        data = {"owner": "bob"}
        assert (await client.post("/api/identity", json=data)).status_code == 403
        assert (
            await client.post(
                "/api/identity",
                json=data,
                headers={"Origin": settings.web_origin, "X-Lab-CSRF": "forged"},
            )
        ).status_code == 403
        headers = {"Origin": settings.web_origin, "X-Lab-CSRF": session["csrf"]}
        for duplicate in ("Origin", "Content-Type", "X-Lab-CSRF"):
            repeated = list(headers.items()) + [("Content-Type", "application/json")]
            repeated.append((duplicate, dict(repeated)[duplicate]))
            assert (
                await client.post("/api/identity", json=data, headers=repeated)
            ).status_code == 403
        changed = await client.post("/api/identity", json=data, headers=headers)
        assert changed.status_code == 200 and changed.json()["owner"] == "bob"
        assert changed.json()["csrf"] != session["csrf"]
        assert (await client.get("/api/task?id=another-session-task")).status_code == 404
        assert (
            await client.post(
                "/api/cancel",
                json={"task_id": "another-session-task"},
                headers={**headers, "X-Lab-CSRF": changed.json()["csrf"]},
            )
        ).status_code == 404
        assert (await client.get("/", headers={"Host": "attacker.invalid"})).status_code == 421
        output = page.text + str(session) + changed.text
        for credential in load_client_keys(settings.credentials_directory).credentials:
            assert credential.token.get_secret_value() not in output


async def test_question_cannot_claim_owner_or_credentials(settings: Settings) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(create_web_app(settings)), base_url=settings.web_origin
    ) as client:
        session = (await client.get("/api/session")).json()
        headers = {"Origin": settings.web_origin, "X-Lab-CSRF": session["csrf"]}
        response = await client.post(
            "/api/ask", headers=headers, json={"text": "security", "owner": "bob"}
        )
        assert response.status_code == 400
        assert (await client.get("/api/session")).json()["tasks"] == []


async def test_expired_credentials_explain_recovery_without_starting_work(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    expiry = load_client_keys(settings.credentials_directory).credentials[0].expires_at
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(create_web_app(settings)), base_url=settings.web_origin
    ) as client:
        session = (await client.get("/api/session")).json()
        monkeypatch.setattr(
            "a2a_lab.security.identity.time", SimpleNamespace(time=lambda: expiry + 1)
        )
        response = await client.post(
            "/api/ask",
            json={"text": "runbook"},
            headers={"Origin": settings.web_origin, "X-Lab-CSRF": session["csrf"]},
        )
        assert response.status_code == 503
        assert "Teaching credentials expired" in response.json()["error"]
        assert "does not renew" in response.json()["error"]
        assert (await client.get("/api/session")).json()["tasks"] == []
