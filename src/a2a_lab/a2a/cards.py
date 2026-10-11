"""Typed Agent Card factories for the two local teaching agents."""

from importlib.metadata import version
from typing import Literal

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

AgentName = Literal["coordinator", "knowledge"]
SKILLS: dict[AgentName, str] = {
    "coordinator": "engineering-coordination",
    "knowledge": "engineering-knowledge",
}


def build_agent_card(agent: AgentName, settings: Settings) -> AgentCard:
    """Advertise text questions and structured, fixture-cited results."""
    description = (
        "Delegate once to the configured knowledge agent and compose its findings."
        if agent == "coordinator"
        else "Match engineering questions to bundled synthetic notes."
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
                id=SKILLS[agent],
                name=f"Engineering {agent}",
                description=description,
                tags=["engineering", "synthetic"],
                examples=[
                    "What information should our service runbook contain?",
                    "[slow] Explain security.",
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
