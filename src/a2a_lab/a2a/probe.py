"""Small SDK compatibility probe; this is not the M2 delegation demo."""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.context import ServerCallContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.common import DefaultServerCallContextBuilder
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    Message,
    Part,
    Role,
    SendMessageRequest,
)
from a2a.utils.errors import InvalidParamsError, UnsupportedOperationError, VersionNotSupportedError
from starlette.applications import Starlette
from starlette.requests import Request

from a2a_lab.config import RPC_PATH, Settings

PROTOCOL_VERSION = "1.0"
PROBE_REPLY = "M1 SDK probe acknowledged the text request."


def build_probe_card(settings: Settings) -> AgentCard:
    """Declare one supported interface and only the probe's actual behavior."""
    return AgentCard(
        name="A2A lab M1 SDK probe",
        description="Loopback-only, unauthenticated compatibility probe for synthetic text.",
        version=version("a2a-lab"),
        supported_interfaces=[
            AgentInterface(
                url=settings.rpc_url,
                protocol_binding="JSONRPC",
                protocol_version=PROTOCOL_VERSION,
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False, push_notifications=False, extended_agent_card=False
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="sdk-probe",
                name="SDK compatibility acknowledgement",
                description="Acknowledge a nonempty text request without tools or delegation.",
                tags=["diagnostics"],
                examples=["Check the A2A SDK integration."],
            )
        ],
    )


class ProbeExecutor(AgentExecutor):
    """Immediate message response, using the SDK executor/event boundary."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        message = context.message
        if message is None or not message.parts:
            raise InvalidParamsError(message="The probe requires a nonempty text message.")
        if any(part.WhichOneof("content") != "text" for part in message.parts):
            raise InvalidParamsError(message="The probe accepts only text parts.")
        text = context.get_user_input()
        if not text.strip() or len(text) > self._settings.max_input_characters:
            raise InvalidParamsError(message="Text is empty or exceeds the configured limit.")
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid4()),
                role=Role.ROLE_AGENT,
                context_id=context.context_id or "",
                parts=[Part(text=PROBE_REPLY)],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise UnsupportedOperationError(message="The immediate M1 probe has no cancellable work.")


class _PinnedVersionContextBuilder(DefaultServerCallContextBuilder):
    """Restrict the SDK's major-version policy to the tested minor version."""

    def build(self, request: Request) -> ServerCallContext:
        actual = request.headers.get("A2A-Version", "")
        # Patch numbers do not affect A2A compatibility. Clients emit plain 1.0.
        if re.fullmatch(rf"{re.escape(PROTOCOL_VERSION)}(?:\.[0-9]+)?", actual) is None:
            raise VersionNotSupportedError(message="This lab interface supports A2A 1.0 only.")
        return super().build(request)


def create_probe_app(settings: Settings) -> Starlette:
    """Wire released SDK routes and drain its handler on application shutdown."""
    card = build_probe_card(settings)
    handler = DefaultRequestHandler(
        agent_executor=ProbeExecutor(settings),
        task_store=InMemoryTaskStore(),
        agent_card=card,
        validate_input_modes=True,
    )

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await handler.aclose()

    return Starlette(
        debug=False,
        routes=[
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(
                handler,
                rpc_url=RPC_PATH,
                context_builder=_PinnedVersionContextBuilder(),
                enable_v0_3_compat=False,
            ),
        ],
        lifespan=lifespan,
    )


async def verify_sdk(
    settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None
) -> dict[str, str]:
    """Resolve and invoke only the configured probe through the official client."""
    async with httpx.AsyncClient(
        transport=transport,
        timeout=settings.request_timeout_seconds,
        trust_env=False,
        follow_redirects=False,
    ) as http_client:
        card = await A2ACardResolver(http_client, settings.base_url).get_agent_card()
        if len(card.supported_interfaces) != 1:
            raise ValueError("The probe must advertise exactly one interface.")
        interface = card.supported_interfaces[0]
        if (
            interface.url != settings.rpc_url
            or interface.protocol_binding != "JSONRPC"
            or interface.protocol_version != PROTOCOL_VERSION
        ):
            raise ValueError("The discovered probe interface does not match the configuration.")
        client = ClientFactory(
            ClientConfig(
                streaming=False,
                httpx_client=http_client,
                supported_protocol_bindings=["JSONRPC"],
                accepted_output_modes=["text/plain"],
            )
        ).create(card)
        try:
            request = SendMessageRequest(
                message=Message(
                    message_id=str(uuid4()), role=Role.ROLE_USER, parts=[Part(text="p")]
                )
            )
            responses = [response async for response in client.send_message(request)]
        finally:
            await client.close()
        if (
            len(responses) != 1
            or not responses[0].HasField("message")
            or len(responses[0].message.parts) != 1
            or responses[0].message.parts[0].text != PROBE_REPLY
        ):
            raise ValueError("The SDK probe did not return the expected acknowledgement.")
    return {
        "result": "ok",
        "sdk_version": version("a2a-sdk"),
        "protocol_version": PROTOCOL_VERSION,
        "binding": "JSONRPC",
        "profile": settings.profile,
        "endpoint": settings.rpc_url,
        "response": PROBE_REPLY,
    }


async def verify_in_process(settings: Settings) -> dict[str, str]:
    """Exercise HTTP serialization with ASGI transport without opening a socket."""
    app = create_probe_app(settings)
    async with app.router.lifespan_context(app):
        report = await verify_sdk(settings, transport=httpx.ASGITransport(app=app))
    return {**report, "transport": "in-process ASGI"}
