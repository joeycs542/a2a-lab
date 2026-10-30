"""Fixed teaching topics selected by trusted startup settings."""

from dataclasses import dataclass
from typing import Literal

from a2a_lab.domain.roles import SpecialistName

DemoScenario = Literal["engineering", "team-lunch"]


@dataclass(frozen=True)
class Topic:
    """Keep displayed capabilities and reference data consistent."""

    name: str
    skill: str
    fixture: str
    source: str
    words: frozenset[str]


TOPICS: dict[DemoScenario, dict[SpecialistName, Topic]] = {
    "engineering": {
        "runbook": Topic(
            "Operations",
            "operations-runbook",
            "runbook",
            "Service runbook",
            frozenset({"runbook", "oncall", "incident", "operations"}),
        ),
        "security": Topic(
            "Security",
            "secure-agent-design",
            "secure-delegation",
            "Secure delegation",
            frozenset({"security", "secure", "approval", "trust"}),
        ),
        "release": Topic(
            "Release",
            "release-readiness",
            "release-readiness",
            "Release readiness checklist",
            frozenset({"release", "readiness", "rollout", "rollback", "deployment"}),
        ),
    },
    "team-lunch": {
        "runbook": Topic(
            "Food",
            "lunch-food",
            "lunch-food",
            "Lunch food options",
            frozenset({"food", "meal", "menu", "dietary", "vegetarian"}),
        ),
        "security": Topic(
            "Budget",
            "lunch-budget",
            "lunch-budget",
            "Lunch budget",
            frozenset({"budget", "cost", "price", "spending", "spend"}),
        ),
        "release": Topic(
            "Place",
            "lunch-place",
            "lunch-place",
            "Lunch places",
            frozenset({"place", "location", "room", "venue", "seats", "where"}),
        ),
    },
}


def section_name(peer: SpecialistName, scenario: DemoScenario) -> str:
    """Preserve existing engineering result headers for the original labs."""
    return TOPICS[scenario][peer].name if scenario == "team-lunch" else peer
