"""Approved-peer discovery and a single bounded SDK request."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.types import AgentCard, Message, Part, Role, SendMessageRequest, TaskState
from a2a.utils.errors import A2AError
from google.protobuf.json_format import MessageToDict

from a2a_lab.a2a.cards import SKILLS, AgentName
from a2a_lab.a2a.limits import BoundaryError, BoundedTransport
from a2a_lab.a2a.protocol import PROTOCOL_VERSION
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.models import Answer

TraceSink = Callable[[str], None]


class LookupFailure(RuntimeError):
    """Discovery or delegation failed without exposing private peer details."""


@dataclass(frozen=True)
class CallResult:
    """Application data and the SDK task identifier from one exchange."""

    answer: Answer
    task_id: str


def validate_card(card: AgentCard, agent: AgentName, settings: Settings) -> None:
    """Check the required capability and exactly the approved interface."""
    if not card.name or not card.description or not card.version:
        raise BoundaryError("Agent Card identity metadata is incomplete.")
    if len(card.supported_interfaces) != 1:
        raise BoundaryError("Agent Card must declare one approved interface.")
    interface = card.supported_interfaces[0]
    if (
        interface.url != f"{settings.agent_base_url(agent)}{RPC_PATH}"
        or interface.protocol_binding != "JSONRPC"
        or interface.protocol_version != PROTOCOL_VERSION
    ):
        raise BoundaryError("Agent Card interface is incompatible or unapproved.")
    skills = [skill for skill in card.skills if skill.id == SKILLS[agent]]
    if len(skills) != 1 or not skills[0].name or not skills[0].description or not skills[0].tags:
        raise BoundaryError("Agent Card lacks the required capability.")
    skill = skills[0]
    if "text/plain" not in (
        skill.input_modes or card.default_input_modes
    ) or "application/json" not in (skill.output_modes or card.default_output_modes):
        raise BoundaryError("Agent Card content modes are incompatible.")
    if card.security_requirements or skill.security_requirements:
        raise BoundaryError("This local client has no authenticated profile.")


class PeerClient:
    """Resolve one configured peer and call it once, without retries."""

    def __init__(
        self,
        settings: Settings,
        agent: AgentName,
        trace: TraceSink,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._trace = trace
        self._transport = transport

    async def answer(self, question: str) -> Answer:
        """Implement the coordinator's knowledge-provider port."""
        return (await self.call(question)).answer

    async def call(self, question: str) -> CallResult:
        """Discover, validate, and invoke; enforce a whole-exchange deadline."""
        if not question.strip() or len(question) > self._settings.max_input_characters:
            raise LookupFailure("Text is empty or exceeds the configured limit.")
        base_url = self._settings.agent_base_url(self._agent)
        card_url = f"{base_url}/.well-known/agent-card.json"
        rpc_url = f"{base_url}{RPC_PATH}"
        boundary = BoundedTransport(
            frozenset({card_url, rpc_url}), self._settings.max_payload_bytes, self._transport
        )
        try:
            async with (
                asyncio.timeout(2 * self._settings.request_timeout_seconds),
                httpx.AsyncClient(
                    transport=boundary,
                    timeout=self._settings.request_timeout_seconds,
                    trust_env=False,
                    follow_redirects=False,
                    headers={"Accept-Encoding": "identity"},
                ) as http_client,
            ):
                self._trace(f"discovery.fetch agent={self._agent} url={card_url}")
                card = await A2ACardResolver(http_client, base_url).get_agent_card()
                validate_card(card, self._agent, self._settings)
                self._trace(f"discovery.approved agent={self._agent} skill={SKILLS[self._agent]}")
                client = ClientFactory(
                    ClientConfig(
                        streaming=False,
                        httpx_client=http_client,
                        supported_protocol_bindings=["JSONRPC"],
                        accepted_output_modes=["application/json"],
                    )
                ).create(card)
                try:
                    self._trace(f"rpc.send agent={self._agent} url={rpc_url}")
                    result: CallResult | None = None
                    request = SendMessageRequest(
                        message=Message(
                            message_id=str(uuid4()),
                            role=Role.ROLE_USER,
                            parts=[Part(text=question)],
                        )
                    )
                    async for response in client.send_message(request):
                        if result is not None or not response.HasField("task"):
                            raise BoundaryError("Peer must return one completed task.")
                        task = response.task
                        if task.status.state != TaskState.TASK_STATE_COMPLETED:
                            raise BoundaryError("Peer task did not complete successfully.")
                        if not task.id or len(task.id) > 128 or len(task.artifacts) != 1:
                            raise BoundaryError("Peer task lacks the expected answer artifact.")
                        artifact = task.artifacts[0]
                        if artifact.name != "engineering-answer" or len(artifact.parts) != 1:
                            raise BoundaryError("Peer answer artifact is malformed.")
                        part = artifact.parts[0]
                        if (
                            part.WhichOneof("content") != "data"
                            or part.media_type != "application/json"
                        ):
                            raise BoundaryError("Peer answer is not structured JSON data.")
                        answer = Answer.model_validate(MessageToDict(part.data))
                        result = CallResult(answer=answer, task_id=task.id)
                    if result is None:
                        raise BoundaryError("Peer returned no answer.")
                    self._trace(f"rpc.completed agent={self._agent} task={result.task_id!r}")
                    return result
                finally:
                    await client.close()
        except asyncio.CancelledError:
            raise
        except (
            A2AError,
            httpx.HTTPError,
            ValueError,
            TypeError,
            AttributeError,
            TimeoutError,
        ) as error:
            # Malformed peer JSON can also raise built-in errors in the SDK resolver.
            self._trace(f"peer.failed agent={self._agent} category={type(error).__name__}")
            raise LookupFailure(
                "Peer unavailable, incompatible, or outside configured limits."
            ) from error
