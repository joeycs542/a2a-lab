"""Exercise the installed review gateway over HTTP without printing credentials.

Feed this script to Python in the Compose client; see Lab 7. It uses synthetic
browser sessions, not the operator bearer bundle or an alternate source import.
"""

import time

import httpx

ORIGIN = "http://127.0.0.1:8080"
BASE = "http://ingress:8080"


def finish(client: httpx.Client, task_id: str) -> dict:
    """Poll one known task within a finite smoke-check budget."""
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        response = client.get("/api/task", params={"id": task_id})
        response.raise_for_status()
        task = response.json()
        if task["state"] in {
            "TASK_STATE_COMPLETED",
            "TASK_STATE_CANCELED",
            "TASK_STATE_FAILED",
            "TASK_STATE_REJECTED",
        }:
            return task
        time.sleep(0.1)
    raise RuntimeError("Browser smoke task exceeded its poll budget.")


with (
    httpx.Client(
        base_url=BASE, headers={"Host": "127.0.0.1:8080"}, trust_env=False, timeout=10
    ) as alice,
    httpx.Client(
        base_url=BASE, headers={"Host": "127.0.0.1:8080"}, trust_env=False, timeout=10
    ) as bob,
):
    page = alice.get("/")
    assert page.status_code == 200 and "HttpOnly" in page.headers["set-cookie"]
    assert "script-src 'self'" in page.headers["content-security-policy"]
    alice_session = alice.get("/api/session").json()
    alice_headers = {"Origin": ORIGIN, "X-Lab-CSRF": alice_session["csrf"]}
    assert alice.post("/api/ask", json={"text": "release"}).status_code == 403
    assert (
        alice.post(
            "/api/ask", json={"text": "release"}, headers={**alice_headers, "Origin": "http://bad"}
        ).status_code
        == 403
    )
    started = alice.post(
        "/api/ask", json={"text": "runbook security release"}, headers=alice_headers
    )
    assert started.status_code == 202, started.text
    task_id = started.json()["task_id"]
    task = finish(alice, task_id)
    assert task["state"] == "TASK_STATE_COMPLETED"
    assert len(task["result"]["references"]) == 3
    assert sum("selection.selected" in event for event in task["events"]) == 3
    assert sum("review.outcome" in event for event in task["events"]) == 3
    session = bob.get("/api/session").json()
    assert bob.get("/api/task", params={"id": task_id}).status_code == 404
    changed = bob.post(
        "/api/identity",
        json={"owner": "bob"},
        headers={"Origin": ORIGIN, "X-Lab-CSRF": session["csrf"]},
    ).json()
    bob_headers = {"Origin": ORIGIN, "X-Lab-CSRF": changed["csrf"]}
    started = bob.post("/api/ask", json={"text": "runbook security release"}, headers=bob_headers)
    assert started.status_code == 202, started.text
    task = finish(bob, started.json()["task_id"])
    assert "Incomplete review" in task["result"]["answer"]
    assert len(task["result"]["references"]) == 2
    assert not any("rpc.send agent=security" in event for event in task["events"])
    started = alice.post("/api/ask", json={"text": "[slow] release"}, headers=alice_headers)
    assert started.status_code == 202
    slow_id = started.json()["task_id"]
    canceled = alice.post("/api/cancel", json={"task_id": slow_id}, headers=alice_headers)
    assert canceled.status_code == 200
    final = finish(alice, slow_id)
    assert final["state"] == "TASK_STATE_CANCELED" and "result" not in final
    print("Browser HTTP smoke passed: review, partial permission, session isolation, CSRF, cancel.")
