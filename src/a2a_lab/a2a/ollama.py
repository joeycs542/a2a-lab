"""Optional bounded loopback inference; the existing workflow owns retrieval."""

import asyncio
import json

import httpx
from pydantic import BaseModel, Field

from a2a_lab.a2a.limits import BoundedTransport
from a2a_lab.agents.prompting import ModelRole, system_prompt
from a2a_lab.config import Settings
from a2a_lab.domain.models import Answer
from a2a_lab.domain.ports import KnowledgeLookup


class _Message(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class _Reply(BaseModel):
    message: _Message
    done: bool


class OllamaWorkflow:
    """Generate one answer from known notes, without granting model authority."""

    def __init__(
        self,
        source: KnowledgeLookup,
        settings: Settings,
        *,
        role: ModelRole = "knowledge",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.source = source
        self.settings = settings
        self.transport = transport
        self.prompt = system_prompt(role, settings.prompt_profile)

    async def answer(self, question: str) -> Answer:
        """No retries or fixture fallback; cancellation stops the local HTTP wait."""
        context = await self.source.answer(question)
        if not context.references:
            return context
        url = f"http://127.0.0.1:{self.settings.ollama_port}/api/chat"
        try:
            async with (
                asyncio.timeout(self.settings.request_timeout_seconds / 3),
                httpx.AsyncClient(
                    transport=BoundedTransport(
                        frozenset({url}), self.settings.max_payload_bytes, self.transport
                    ),
                    timeout=self.settings.request_timeout_seconds / 3,
                    trust_env=False,
                    follow_redirects=False,
                    headers={"Accept-Encoding": "identity"},
                ) as client,
            ):
                response = await client.post(
                    url,
                    json={
                        "model": self.settings.ollama_model,
                        "stream": False,
                        "think": False,
                        "keep_alive": "5m",
                        "options": {"num_predict": 256, "num_ctx": 4096, "temperature": 0.2},
                        "messages": [
                            {
                                "role": "system",
                                "content": self.prompt,
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {"question": question, "notes": context.answer}
                                ),
                            },
                        ],
                    },
                )
                response.raise_for_status()
                reply = _Reply.model_validate(response.json())
                if not reply.done or not reply.message.content.strip():
                    raise ValueError("Incomplete model response.")
                return Answer(answer=reply.message.content, references=context.references)
        except (httpx.HTTPError, TimeoutError, ValueError) as error:
            raise ValueError(
                "Local inference unavailable or returned an invalid answer."
            ) from error
