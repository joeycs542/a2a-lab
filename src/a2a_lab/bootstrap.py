"""Construct teaching workflows without mixing domain and SDK contracts."""

from starlette.applications import Starlette

from a2a_lab.a2a.cards import AgentName
from a2a_lab.a2a.client import PeerClient
from a2a_lab.a2a.server import console_trace, create_agent_app
from a2a_lab.agents.coordinator import CoordinatorAgent
from a2a_lab.agents.knowledge import KnowledgeAgent
from a2a_lab.config import Settings
from a2a_lab.domain.ports import KnowledgeLookup
from a2a_lab.security.identity import load_server_keys


def build_app(agent: AgentName, settings: Settings) -> Starlette:
    """Build either an offline knowledge workflow or one-hop coordinator."""
    trace = console_trace(agent)
    keys = (
        load_server_keys(settings.credentials_directory, agent)
        if settings.profile == "local-secure"
        else None
    )
    workflow: KnowledgeLookup = (
        KnowledgeAgent(settings.fixture_delay_seconds)
        if agent == "knowledge"
        else CoordinatorAgent(PeerClient(settings, "knowledge", trace, server_keys=keys))
    )
    return create_agent_app(agent, settings, workflow, trace, keys=keys)
