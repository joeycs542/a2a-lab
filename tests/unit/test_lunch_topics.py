"""Scenario selection changes content, not authority or endpoint selection."""

import pytest
from pydantic import ValidationError

from a2a_lab.agents.prompting import system_prompt
from a2a_lab.agents.specialist import SpecialistAgent
from a2a_lab.config import Settings
from a2a_lab.domain.discovery import topic_scores


def test_lunch_routes_only_lunch_topics() -> None:
    assert topic_scores("Suggest food for our team lunch.", "team-lunch") == {
        "runbook": 1,
        "security": 0,
        "release": 0,
    }
    assert all(topic_scores("Plan a team lunch.", "team-lunch").values())
    assert not any(topic_scores("security release runbook", "team-lunch").values())
    assert not any(topic_scores("food budget place").values())


def test_lunch_requires_discovery() -> None:
    with pytest.raises(ValidationError, match="requires the discovery topology"):
        Settings(_env_file=None, demo_scenario="team-lunch")


async def test_lunch_guide_and_source_agree() -> None:
    answer = await SpecialistAgent("runbook", scenario="team-lunch").answer("food")
    assert answer.references[0].fixture_id == "lunch-food"
    prompt = system_prompt("food", "guided")
    assert "Food agent" in prompt and "vegetarian" in prompt
    assert "operations specialist" not in prompt
