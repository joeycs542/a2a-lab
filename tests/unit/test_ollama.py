"""Optional inference keeps known provenance and fails closed."""

import asyncio
import json

import httpx
import pytest

from a2a_lab.a2a.ollama import OllamaWorkflow
from a2a_lab.agents.specialist import SpecialistAgent
from a2a_lab.config import Settings


async def test_generated_answer_preserves_context_reference() -> None:
    def reply(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert body["model"] == "qwen3:0.6b"
        assert body["stream"] is False and body["think"] is False
        assert "runbook" in body["messages"][1]["content"]
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"done": True, "message": {"content": "## Generated"}})

    workflow = OllamaWorkflow(
        SpecialistAgent("runbook"), Settings(_env_file=None), transport=httpx.MockTransport(reply)
    )
    answer = await workflow.answer("What belongs in a runbook?")
    assert answer.answer == "## Generated"
    assert answer.references[0].fixture_id == "runbook"


@pytest.mark.parametrize(
    "payload",
    [
        {"done": False, "message": {"content": "partial"}},
        {"done": True, "message": {"content": " "}},
        {"done": True, "message": {"content": "x" * 2001}},
        {"error": "missing model"},
    ],
)
async def test_invalid_model_output_does_not_fall_back(payload: dict[str, object]) -> None:
    workflow = OllamaWorkflow(
        SpecialistAgent("runbook"),
        Settings(_env_file=None),
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
    )
    with pytest.raises(ValueError, match="Local inference"):
        await workflow.answer("runbook")


async def test_unavailable_runtime_fails_without_fixture_fallback() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    workflow = OllamaWorkflow(
        SpecialistAgent("runbook"), Settings(_env_file=None), transport=httpx.MockTransport(fail)
    )
    with pytest.raises(ValueError, match="Local inference"):
        await workflow.answer("runbook")


async def test_cancellation_propagates() -> None:
    started = asyncio.Event()

    async def wait(request: httpx.Request) -> httpx.Response:
        started.set()
        await asyncio.Event().wait()
        return httpx.Response(200)

    workflow = OllamaWorkflow(
        SpecialistAgent("runbook"), Settings(_env_file=None), transport=httpx.MockTransport(wait)
    )
    task = asyncio.create_task(workflow.answer("runbook"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
