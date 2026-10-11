"""Approved-peer discovery, lifecycle calls, and bounded delegation."""

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, Client, ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    CancelTaskRequest,
    GetTaskRequest,
    ListTasksRequest,
    ListTasksResponse,
    Message,
    Part,
    Role,
    SendMessageConfiguration,
    SendMessageRequest,
    Task,
    TaskState,
)
from a2a.utils.errors import A2AError
from google.protobuf.json_format import MessageToDict

from a2a_lab.a2a.cards import AgentName, required_skill_id
from a2a_lab.a2a.limits import BoundaryError, BoundedTransport
from a2a_lab.a2a.protocol import PROTOCOL_VERSION
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.models import Answer
from a2a_lab.security.identity import (
    Credential,
    Owner,
    SecurityError,
    ServerKeys,
    current_principal,
    load_client_keys,
)

TraceSink = Callable[[str], None]
TERMINAL = frozenset(
    {
        TaskState.TASK_STATE_COMPLETED,
        TaskState.TASK_STATE_FAILED,
        TaskState.TASK_STATE_CANCELED,
        TaskState.TASK_STATE_REJECTED,
    }
)


class LookupFailure(RuntimeError):
    """Discovery or delegation failed without exposing private peer details."""


@dataclass(frozen=True)
class CallResult:
    """Application data and the SDK task identifier from one exchange."""

    answer: Answer
    task_id: str


def validate_card(card: AgentCard, agent: AgentName, settings: Settings) -> None:
    """Check the required capability, security profile, and approved interface."""
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
    skills = [skill for skill in card.skills if skill.id == required_skill_id(agent, settings)]
    if len(skills) != 1 or not skills[0].name or not skills[0].description or not skills[0].tags:
        raise BoundaryError("Agent Card lacks the required capability.")
    skill = skills[0]
    if "text/plain" not in (
        skill.input_modes or card.default_input_modes
    ) or "application/json" not in (skill.output_modes or card.default_output_modes):
        raise BoundaryError("Agent Card content modes are incompatible.")
    if settings.profile == "local-secure":
        if (
            len(card.security_requirements) != 1
            or set(card.security_requirements[0].schemes) != {"localBearer"}
            or list(card.security_requirements[0].schemes["localBearer"].list)
            or set(card.security_schemes) != {"localBearer"}
            or card.security_schemes["localBearer"].WhichOneof("scheme")
            != "http_auth_security_scheme"
            or card.security_schemes["localBearer"].http_auth_security_scheme.scheme != "bearer"
            or skill.security_requirements
        ):
            raise BoundaryError("Agent Card does not match the configured bearer profile.")
    elif card.security_requirements or skill.security_requirements:
        raise BoundaryError("This local client has no authenticated profile.")


def read_answer(task: Task) -> CallResult:
    """Validate the one supported completed answer artifact as data."""
    if task.status.state != TaskState.TASK_STATE_COMPLETED:
        raise BoundaryError("Peer task did not complete successfully.")
    if not task.id or len(task.id) > 128 or len(task.artifacts) != 1:
        raise BoundaryError("Peer task lacks the expected answer artifact.")
    artifact = task.artifacts[0]
    if artifact.name != "engineering-answer" or len(artifact.parts) != 1:
        raise BoundaryError("Peer answer artifact is malformed.")
    part = artifact.parts[0]
    if part.WhichOneof("content") != "data" or part.media_type != "application/json":
        raise BoundaryError("Peer answer is not structured JSON data.")
    return CallResult(answer=Answer.model_validate(MessageToDict(part.data)), task_id=task.id)


class PeerClient:
    """Use configured credentials, one send, and bounded lifecycle operations."""

    def __init__(
        self,
        settings: Settings,
        agent: AgentName,
        trace: TraceSink,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        owner: Owner = "alice",
        server_keys: ServerKeys | None = None,
        credential: Credential | None = None,
    ) -> None:
        self._settings = settings
        self._agent = agent
        self._trace = trace
        self._transport = transport
        self._owner = owner
        self._server_keys = server_keys
        self._explicit_credential = credential

    def _credential(self) -> Credential | None:
        if self._settings.profile != "local-secure":
            return None
        if self._explicit_credential is not None:
            credential = self._explicit_credential
        elif self._server_keys is not None:
            principal = current_principal.get()
            if principal is None or principal.role != "user":
                raise SecurityError("Delegation requires a verified user.")
            credential = self._server_keys.delegated(principal.owner)
        else:
            credential = load_client_keys(self._settings.credentials_directory).select(
                self._owner, self._agent
            )
        if credential.principal.audience != self._agent:
            raise SecurityError("Credential recipient does not match the configured peer.")
        return credential

    @asynccontextmanager
    async def _connected(self, credential: Credential | None) -> AsyncIterator[Client]:
        base_url = self._settings.agent_base_url(self._agent)
        card_url, rpc_url = f"{base_url}/.well-known/agent-card.json", f"{base_url}{RPC_PATH}"
        headers = {"Accept-Encoding": "identity"}
        if credential is not None:
            headers["Authorization"] = credential.bearer()
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
                    headers=headers,
                ) as http_client,
            ):
                self._trace(f"discovery.fetch agent={self._agent} url={card_url}")
                card = await A2ACardResolver(http_client, base_url).get_agent_card()
                validate_card(card, self._agent, self._settings)
                self._trace(
                    f"discovery.approved agent={self._agent} "
                    f"skill={required_skill_id(self._agent, self._settings)}"
                )
                client = ClientFactory(
                    ClientConfig(
                        streaming=False,
                        httpx_client=http_client,
                        supported_protocol_bindings=["JSONRPC"],
                        accepted_output_modes=["application/json"],
                    )
                ).create(card)
                try:
                    yield client
                finally:
                    await client.close()
        except (
            A2AError,
            httpx.HTTPError,
            ValueError,
            TypeError,
            AttributeError,
            TimeoutError,
        ) as error:
            self._trace(f"peer.failed agent={self._agent} category={type(error).__name__}")
            raise LookupFailure(
                "Peer unavailable, incompatible, or outside configured limits."
            ) from error

    async def _send(self, question: str, credential: Credential | None, immediate: bool) -> Task:
        if not question.strip() or len(question) > self._settings.max_input_characters:
            raise LookupFailure("Text is empty or exceeds the configured limit.")
        async with self._connected(credential) as client:
            request = SendMessageRequest(
                message=Message(
                    message_id=str(uuid4()), role=Role.ROLE_USER, parts=[Part(text=question)]
                ),
                configuration=SendMessageConfiguration(
                    return_immediately=immediate, history_length=0
                ),
            )
            self._trace(
                f"rpc.send agent={self._agent} "
                f"url={self._settings.agent_base_url(self._agent)}{RPC_PATH}"
            )
            task: Task | None = None
            async for response in client.send_message(request):
                if task is not None or not response.HasField("task"):
                    raise BoundaryError("Peer must return one SDK task.")
                task = response.task
                if not task.id or len(task.id) > 128:
                    raise BoundaryError("Peer task identifier is invalid.")
            if task is None:
                raise BoundaryError("Peer returned no task.")
            return task

    async def answer(self, question: str) -> Answer:
        """Implement the coordinator's knowledge-provider port."""
        return (await self.call(question)).answer

    async def start(self, question: str) -> Task:
        """Start one task without waiting for its terminal state."""
        return await self._send(question, self._credential(), True)

    async def get_task(self, task_id: str) -> Task:
        """Retrieve a task using this client's configured identity."""
        async with self._connected(self._credential()) as client:
            return await client.get_task(GetTaskRequest(id=task_id, history_length=0))

    async def cancel_task(self, task_id: str) -> Task:
        """Cancel owned work through the SDK, without retries."""
        async with self._connected(self._credential()) as client:
            return await client.cancel_task(CancelTaskRequest(id=task_id))

    async def list_tasks(self) -> ListTasksResponse:
        """List a bounded, owner-scoped first page without artifacts/history."""
        async with self._connected(self._credential()) as client:
            return await client.list_tasks(
                ListTasksRequest(page_size=25, history_length=0, include_artifacts=False)
            )

    async def _cleanup(self, task_id: str, credential: Credential | None) -> None:
        try:
            async with asyncio.timeout(min(1.0, self._settings.request_timeout_seconds)):
                async with self._connected(credential) as client:
                    await client.cancel_task(CancelTaskRequest(id=task_id))
            self._trace(f"delegation.cancelled agent={self._agent} task={task_id!r}")
        except (LookupFailure, TimeoutError, SecurityError):
            self._trace(f"delegation.cancel_unknown agent={self._agent} task={task_id!r}")

    async def call(self, question: str) -> CallResult:
        """Send once; authenticated delegation polls and cancels on interruption."""
        credential = self._credential()
        task: Task | None = None
        try:
            async with asyncio.timeout(2 * self._settings.request_timeout_seconds):
                task = await self._send(
                    question, credential, self._settings.profile == "local-secure"
                )
                if self._settings.profile == "local-secure":
                    for _ in range(self._settings.max_task_polls):
                        if task.status.state in TERMINAL:
                            break
                        await asyncio.sleep(0.05)
                        async with self._connected(credential) as client:
                            task = await client.get_task(
                                GetTaskRequest(id=task.id, history_length=0)
                            )
                    if task.status.state not in TERMINAL:
                        raise LookupFailure("Task polling budget exceeded.")
                result = read_answer(task)
                self._trace(f"rpc.completed agent={self._agent} task={result.task_id!r}")
                return result
        except (ValueError, TimeoutError) as error:
            raise LookupFailure("Peer task failed or exceeded its deadline.") from error
        finally:
            if task is not None and task.status.state not in TERMINAL:
                cleanup = asyncio.create_task(self._cleanup(task.id, credential))
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    cleanup.cancel()
                    await asyncio.gather(cleanup, return_exceptions=True)
