"""Assemble SDK routes with bounded local workflow execution."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes.agent_card_routes import create_agent_card_routes
from a2a.server.routes.jsonrpc_routes import create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from starlette.applications import Starlette
from starlette.middleware import Middleware

from a2a_lab.a2a.cards import AgentName, build_agent_card
from a2a_lab.a2a.client import TraceSink
from a2a_lab.a2a.executor import WorkflowExecutor
from a2a_lab.a2a.limits import RequestLimits
from a2a_lab.a2a.protocol import PinnedVersionContextBuilder
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.ports import KnowledgeLookup


def console_trace(agent: AgentName) -> TraceSink:
    """Emit fixed event fields without user text, cards, or credentials."""

    def emit(event: str) -> None:
        print(f"[{agent} pid={os.getpid()}] {event}", flush=True)

    return emit


def create_agent_app(
    agent: AgentName, settings: Settings, workflow: KnowledgeLookup, trace: TraceSink
) -> Starlette:
    """Give each process an independent SDK task store and lifespan owner."""
    card = build_agent_card(agent, settings)
    handler = DefaultRequestHandler(
        agent_executor=WorkflowExecutor(workflow, settings, trace),
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
                context_builder=PinnedVersionContextBuilder(),
                enable_v0_3_compat=False,
            ),
        ],
        middleware=[Middleware(RequestLimits, settings=settings)],
        lifespan=lifespan,
    )
