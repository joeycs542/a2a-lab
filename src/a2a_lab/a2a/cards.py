"""Typed Agent Cards for baseline and discovery teaching agents."""

from importlib.metadata import version

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    HTTPAuthSecurityScheme,
    SecurityRequirement,
    SecurityScheme,
    StringList,
)

from a2a_lab.a2a.protocol import PROTOCOL_VERSION
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.roles import AgentName as AgentName
from a2a_lab.domain.scenarios import TOPICS

SKILLS: dict[AgentName, str] = {
    "coordinator": "engineering-coordination",
    "knowledge": "engineering-knowledge",
    "runbook": "operations-runbook",
    "security": "secure-agent-design",
    "release": "release-readiness",
}


def required_skill_id(agent: AgentName, settings: Settings) -> str:
    """Select the expected capability from trusted workflow configuration."""
    if agent == "coordinator" and settings.topology == "discovery":
        if settings.demo_scenario == "team-lunch":
            return "team-lunch-plan" if settings.discovery_mode == "review" else "team-lunch-help"
        return (
            "engineering-review" if settings.discovery_mode == "review" else "engineering-discovery"
        )
    if agent == "knowledge" and settings.knowledge_workflow == "release-readiness":
        return "release-readiness"
    if settings.demo_scenario == "team-lunch" and (
        agent == "runbook" or agent == "security" or agent == "release"
    ):
        return TOPICS["team-lunch"][agent].skill
    return SKILLS[agent]


def build_agent_card(agent: AgentName, settings: Settings) -> AgentCard:
    """Advertise text questions and structured, fixture-cited results."""
    description = (
        "Delegate once to the configured knowledge agent and compose its findings."
        if agent == "coordinator"
        else "Match engineering questions to bundled synthetic notes."
    )
    if agent == "knowledge" and settings.knowledge_workflow == "release-readiness":
        description = "Return a bundled release readiness checklist without approving deployments."
    question = (
        "What should we review before a release?"
        if settings.knowledge_workflow == "release-readiness"
        else "What information should our service runbook contain?"
    )
    if agent == "runbook" or agent == "security" or agent == "release":
        description = (
            f"Return bundled {agent} guidance without inspecting systems or authorizing actions."
        )
        question = {
            "runbook": "What belongs in a runbook?",
            "security": "How should we design secure delegation?",
            "release": "What should we review before a release?",
        }[agent]
    if agent == "coordinator" and settings.topology == "discovery":
        description = (
            "Consult up to three approved specialists and report attributed partial outcomes."
            if settings.discovery_mode == "review"
            else "Search an approved directory, validate live cards and select one specialist."
        )
        question = (
            "Review runbook, security and release readiness."
            if settings.discovery_mode == "review"
            else "What belongs in a runbook?"
        )
    display_name = f"A2A lab {agent}"
    if settings.demo_scenario == "team-lunch":
        if agent == "runbook" or agent == "security" or agent == "release":
            topic = TOPICS["team-lunch"][agent]
            display_name = f"Team lunch {topic.name} agent"
            description = (
                f"Give {topic.name.lower()} advice from fictional lunch notes. "
                "No bookings or purchases."
            )
            question = {
                "runbook": "Suggest food for our team lunch.",
                "security": "What is our lunch budget?",
                "release": "Where can we have our team lunch? Name a place.",
            }[agent]
        elif agent == "coordinator":
            display_name = "Team lunch coordinator"
            description = (
                "Find permitted food, place and budget agents. Return their answers to the user."
            )
            question = "Plan a team lunch: food, place, and budget."
    if settings.inference_backend == "ollama" and agent != "coordinator":
        description = (
            "Generate a concise answer using a local model and bundled synthetic notes. "
            "Does not inspect systems or authorize actions."
        )
    card = AgentCard(
        name=display_name,
        description=f"{description} Synthetic {settings.profile} loopback profile.",
        version=version("a2a-lab"),
        supported_interfaces=[
            AgentInterface(
                url=f"{settings.agent_base_url(agent)}{RPC_PATH}",
                protocol_binding="JSONRPC",
                protocol_version=PROTOCOL_VERSION,
            )
        ],
        capabilities=AgentCapabilities(
            streaming=False, push_notifications=False, extended_agent_card=False
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id=required_skill_id(agent, settings),
                name=display_name
                if settings.demo_scenario == "team-lunch"
                else f"Engineering {agent}",
                description=description,
                tags=[settings.demo_scenario, "synthetic"],
                examples=[
                    question,
                    f"[slow] {question}",
                    "[fail] Exercise a controlled failure.",
                ],
                input_modes=["text/plain"],
                output_modes=["application/json"],
            )
        ],
    )
    if settings.profile == "local-secure":
        card.security_schemes["localBearer"].CopyFrom(
            SecurityScheme(
                http_auth_security_scheme=HTTPAuthSecurityScheme(
                    scheme="bearer",
                    bearer_format="opaque",
                    description="Locally issued recipient-bound credential.",
                )
            )
        )
        card.security_requirements.append(
            SecurityRequirement(schemes={"localBearer": StringList()})
        )
    return card
