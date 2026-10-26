import httpx

from a2a_lab.a2a.client import PeerClient
from a2a_lab.a2a.server import create_agent_app
from a2a_lab.agents.knowledge import KnowledgeAgent
from a2a_lab.config import Settings
from a2a_lab.security.identity import load_client_keys


async def test_http_human_control_and_exact_release(secure_settings: Settings) -> None:
    events: list[str] = []
    app = create_agent_app("coordinator", secure_settings, KnowledgeAgent(), events.append)
    keys = load_client_keys(secure_settings.credentials_directory)
    user = {"Authorization": keys.select("alice", "coordinator").bearer()}
    human = {"Authorization": keys.select("alice", "coordinator", approval=True).bearer()}
    wrong_user = {"Authorization": keys.select("bob", "coordinator").bearer()}
    wrong_human = {"Authorization": keys.select("bob", "coordinator", approval=True).bearer()}
    peer = PeerClient(
        secure_settings, "coordinator", events.append, transport=httpx.ASGITransport(app=app)
    )
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=secure_settings.agent_base_url("coordinator"),
        ) as client,
    ):
        result = await peer.call("runbook")
        stored = await peer.get_task(result.task_id)
        terms = {
            "task_id": result.task_id,
            "artifact_id": stored.artifacts[0].artifact_id,
            "label": "Reviewed synthetic fixture",
        }
        assert (
            await client.post("/actions/proposals", headers=wrong_user, json=terms)
        ).status_code == 403
        proposal_response = await client.post("/actions/proposals", headers=user, json=terms)
        assert proposal_response.status_code == 200
        proposal = proposal_response.json()
        execution = {
            "proposal_id": proposal["proposal_id"],
            "approval_id": "generated-approval-flag",
            "idempotency_key": "one-release",
            "terms": proposal["terms"],
        }
        assert (
            await client.post("/actions/execute", headers=user, json=execution)
        ).status_code == 403
        approval = {
            "proposal_id": proposal["proposal_id"],
            "expected_digest": proposal["digest"],
            "terms": proposal["terms"],
        }
        assert (
            await client.post("/control/approve", headers=user, json=approval)
        ).status_code == 403
        assert (
            await client.post("/control/approve", headers=wrong_human, json=approval)
        ).status_code == 403
        assert (
            await client.post(
                "/control/approve", headers=human, json={**approval, "approved": True}
            )
        ).status_code == 422
        changed = {**proposal["terms"], "label": "Changed after review"}
        assert (
            await client.post(
                "/control/approve", headers=human, json={**approval, "terms": changed}
            )
        ).status_code == 403
        grant_response = await client.post("/control/approve", headers=human, json=approval)
        assert grant_response.status_code == 200
        grant = grant_response.json()
        execution["approval_id"] = grant["approval_id"]
        assert (
            await client.post(
                "/actions/execute", headers=user, json={**execution, "terms": changed}
            )
        ).status_code == 403
        released = await client.post("/actions/execute", headers=user, json=execution)
        assert released.status_code == 200
        assert "runbook" in released.json()["fixture"]["answer"].lower()
        retry = await client.post("/actions/execute", headers=user, json=execution)
        assert retry.json()["release_id"] == released.json()["release_id"]
        assert (
            await client.post(
                "/actions/execute", headers=user, json={**execution, "idempotency_key": "replay"}
            )
        ).status_code == 403
        assert (
            await client.post("/actions/execute", headers=wrong_user, json=execution)
        ).status_code == 403
        denied_rpc = await client.post(
            "/a2a/jsonrpc",
            headers={**human, "A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "human-cannot-act-as-agent",
                "method": "GetTask",
                "params": {"id": result.task_id},
            },
        )
        assert denied_rpc.status_code == 403
        continuation = await client.post(
            "/a2a/jsonrpc",
            headers={**user, "A2A-Version": "1.0"},
            json={
                "jsonrpc": "2.0",
                "id": "no-mutation",
                "method": "SendMessage",
                "params": {
                    "message": {
                        "messageId": "mutation",
                        "taskId": result.task_id,
                        "role": "ROLE_USER",
                        "parts": [{"text": "replace this artifact"}],
                    }
                },
            },
        )
        assert "error" in continuation.json()
    trace = "\n".join(events)
    assert all(credential.token.get_secret_value() not in trace for credential in keys.credentials)


async def test_card_advertises_authentication_without_credentials(
    secure_settings: Settings,
) -> None:
    app = create_agent_app("knowledge", secure_settings, KnowledgeAgent(), lambda event: None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app)) as client:
        response = await client.get(
            secure_settings.agent_base_url("knowledge") + "/.well-known/agent-card.json"
        )
    card = response.json()
    assert card["securitySchemes"]["localBearer"]["httpAuthSecurityScheme"]["scheme"] == "bearer"
    assert card["securityRequirements"][0]["schemes"] == {"localBearer": {}}
    assert all(
        credential.token.get_secret_value() not in response.text
        for credential in load_client_keys(secure_settings.credentials_directory).credentials
    )


async def test_unlisted_routes_and_methods_do_not_inherit_authority(
    secure_settings: Settings,
) -> None:
    app = create_agent_app("coordinator", secure_settings, KnowledgeAgent(), lambda event: None)
    keys = load_client_keys(secure_settings.credentials_directory)
    user = {"Authorization": keys.select("alice", "coordinator").bearer()}
    human = {"Authorization": keys.select("alice", "coordinator", approval=True).bearer()}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=secure_settings.agent_base_url("coordinator"),
    ) as client:
        assert (await client.post("/future-tool", headers=user)).status_code == 403
        assert (await client.get("/a2a/jsonrpc", headers=user)).status_code == 403
        assert (await client.post("/control/unlisted", headers=human)).status_code == 403
