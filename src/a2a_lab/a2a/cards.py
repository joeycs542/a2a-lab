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
        return (
            "engineering-review" if settings.discovery_mode == "review" else "engineering-discovery"
        )
    if agent == "knowledge" and settings.knowledge_workflow == "release-readiness":
        return "release-readiness"
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
    if agent in {"runbook", "security", "release"}:
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
    card = AgentCard(
        name=f"A2A lab {agent}",
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
                name=f"Engineering {agent}",
                description=description,
                tags=["engineering", "synthetic"],
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
