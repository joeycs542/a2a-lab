"""Assemble SDK routes with bounded local workflow execution."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from a2a.server.context import ServerCallContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.types import Message, SendMessageRequest, Task
from a2a.utils.errors import InternalError, UnsupportedOperationError
from starlette.applications import Starlette
from starlette.middleware import Middleware

from a2a_lab.a2a.actions import ActionRoutes
from a2a_lab.a2a.cards import AgentName, build_agent_card
from a2a_lab.a2a.client import TraceSink
from a2a_lab.a2a.executor import WorkflowExecutor
from a2a_lab.a2a.identity import AuthenticatedContextBuilder
from a2a_lab.a2a.limits import RequestLimits
from a2a_lab.a2a.protocol import PinnedVersionContextBuilder
from a2a_lab.a2a.store import BoundedTaskStore
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.ports import KnowledgeLookup
from a2a_lab.security.approval import ApprovalStore
from a2a_lab.security.http import LocalAuthentication
from a2a_lab.security.identity import ServerKeys, current_correlation, load_server_keys


class LabRequestHandler(DefaultRequestHandler):
    """The lab accepts new questions and does not mutate completed tasks."""

    async def on_message_send(
        self, params: SendMessageRequest, context: ServerCallContext
    ) -> Message | Task:
        if params.message.task_id:
            raise UnsupportedOperationError(message="Task continuation is not a lab capability.")
        result = await super().on_message_send(params, context)
        if not isinstance(result, (Message, Task)):
            raise InternalError(message="SDK returned an unexpected response type.")
        return result


def console_trace(agent: AgentName) -> TraceSink:
    """Emit fixed event fields without user text, cards, or credentials."""

    def emit(event: str) -> None:
        suffix = (
            ""
            if event.startswith(("policy.", "action.", "workflow.started"))
            else f" request={current_correlation.get()}"
        )
        print(f"[{agent} pid={os.getpid()}] {event}{suffix}", flush=True)

    return emit


def create_agent_app(
    agent: AgentName,
    settings: Settings,
    workflow: KnowledgeLookup,
    trace: TraceSink,
    *,
    keys: ServerKeys | None = None,
) -> Starlette:
    """Give each process an independent SDK task store and lifespan owner."""
    card = build_agent_card(agent, settings)
    tasks = BoundedTaskStore(settings.max_retained_tasks)
    handler = LabRequestHandler(
        agent_executor=WorkflowExecutor(workflow, settings, trace),
        task_store=tasks,
        agent_card=card,
        validate_input_modes=True,
    )

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await handler.aclose()

    middleware = [Middleware(RequestLimits, settings=settings)]
    controls = []
    context_builder: PinnedVersionContextBuilder = PinnedVersionContextBuilder()
    if settings.profile == "local-secure":
        keys = keys or load_server_keys(settings.credentials_directory, agent)
        middleware.insert(
            0, Middleware(LocalAuthentication, keys=keys, audience=agent, trace=trace)
        )
        context_builder = AuthenticatedContextBuilder()
        if agent == "coordinator":
            controls = ActionRoutes(
                tasks, ApprovalStore(settings.max_approval_records), trace
            ).routes()

    return Starlette(
        debug=False,
        routes=[
            *create_agent_card_routes(card),
            *create_jsonrpc_routes(
                handler,
                rpc_url=RPC_PATH,
                context_builder=context_builder,
                enable_v0_3_compat=False,
            ),
            *controls,
        ],
        middleware=middleware,
        lifespan=lifespan,
    )
