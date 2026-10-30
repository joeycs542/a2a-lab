"""Construct teaching workflows without mixing domain and SDK contracts."""

from starlette.applications import Starlette

from a2a_lab.a2a.client import PeerClient
from a2a_lab.a2a.directory import DiscoveryLookup, create_directory_app
from a2a_lab.a2a.ollama import OllamaWorkflow
from a2a_lab.a2a.server import console_trace, create_agent_app
from a2a_lab.agents.coordinator import CoordinatorAgent
from a2a_lab.agents.knowledge import KnowledgeAgent
from a2a_lab.agents.prompting import ModelRole
from a2a_lab.agents.readiness import ReleaseReadinessAgent
from a2a_lab.agents.specialist import SpecialistAgent
from a2a_lab.config import Settings
from a2a_lab.domain.ports import KnowledgeLookup
from a2a_lab.domain.roles import ServiceName
from a2a_lab.security.identity import SecurityError, load_server_keys


def build_app(agent: ServiceName, settings: Settings) -> Starlette:
    """Build either an offline knowledge workflow or one-hop coordinator."""
    if agent not in {"coordinator", "knowledge"} and settings.topology != "discovery":
        raise SecurityError("Specialists and directory require the discovery topology.")
    trace = console_trace(agent)
    keys = (
        load_server_keys(settings.credentials_directory, agent)
        if settings.profile == "local-secure"
        else None
    )
    if agent == "directory":
        if keys is None:
            raise SecurityError("The directory requires authenticated credentials.")
        return create_directory_app(settings, keys, trace)
    workflow: KnowledgeLookup
    if agent == "coordinator":
        if settings.topology == "discovery":
            if keys is None:
                raise SecurityError("Discovery requires authenticated credentials.")
            for owner in ("alice", "bob"):
                keys.delegated(owner, "directory")
                for audience in settings.discovery_peers:
                    keys.delegated(owner, audience)
            workflow = DiscoveryLookup(settings, keys, trace)
        else:
            workflow = CoordinatorAgent(PeerClient(settings, "knowledge", trace, server_keys=keys))
    elif agent == "runbook" or agent == "security" or agent == "release":
        workflow = SpecialistAgent(agent, settings.fixture_delay_seconds, settings.demo_scenario)
    elif settings.knowledge_workflow == "release-readiness":
        workflow = ReleaseReadinessAgent(settings.fixture_delay_seconds)
    else:
        workflow = KnowledgeAgent(settings.fixture_delay_seconds)
    if settings.inference_backend == "ollama" and agent != "coordinator":
        role: ModelRole = agent
        if settings.demo_scenario == "team-lunch":
            lunch_roles: dict[str, ModelRole] = {
                "runbook": "food",
                "security": "budget",
                "release": "place",
                "knowledge": "knowledge",
            }
            role = lunch_roles[agent]
        workflow = OllamaWorkflow(workflow, settings, role=role)
    return create_agent_app(agent, settings, workflow, trace, keys=keys)
