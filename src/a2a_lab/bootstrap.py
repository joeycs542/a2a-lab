"""Construct teaching workflows without mixing domain and SDK contracts."""

from starlette.applications import Starlette

from a2a_lab.a2a.cards import AgentName
from a2a_lab.a2a.client import PeerClient
from a2a_lab.a2a.server import console_trace, create_agent_app
from a2a_lab.agents.coordinator import CoordinatorAgent
from a2a_lab.agents.knowledge import KnowledgeAgent
from a2a_lab.config import Settings
from a2a_lab.domain.ports import KnowledgeLookup


def build_app(agent: AgentName, settings: Settings) -> Starlette:
    """Build either an offline knowledge workflow or one-hop coordinator."""
    trace = console_trace(agent)
    workflow: KnowledgeLookup = (
        KnowledgeAgent()
        if agent == "knowledge"
        else CoordinatorAgent(PeerClient(settings, "knowledge", trace))
    )
    return create_agent_app(agent, settings, workflow, trace)
