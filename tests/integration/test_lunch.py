"""The everyday scenario uses real A2A and the existing permission boundary."""

import socket
from contextlib import ExitStack
from pathlib import Path

import pytest

from a2a_lab.a2a.client import LookupFailure, PeerClient
from a2a_lab.config import Settings
from a2a_lab.demo import running_agents
from a2a_lab.domain.roles import services_for
from a2a_lab.security.identity import initialize_security


async def test_lunch_answers_and_budget_permission(tmp_path: Path) -> None:
    credentials = tmp_path / "keys"
    initialize_security(credentials, topology="discovery")
    ports = {}
    with ExitStack() as stack:
        for service in services_for("discovery"):
            listener = stack.enter_context(socket.socket())
            listener.bind(("127.0.0.1", 0))
            ports[f"{service}_port"] = listener.getsockname()[1]
    settings = Settings(
        _env_file=None,
        profile="local-secure",
        topology="discovery",
        discovery_mode="review",
        demo_scenario="team-lunch",
        credentials_directory=credentials,
        **ports,
    )
    events: list[str] = []
    async with running_agents(settings, events.append):
        alice = PeerClient(settings, "coordinator", events.append)
        food = await alice.call("Suggest food for our team lunch.")
        assert [ref.fixture_id for ref in food.answer.references] == ["lunch-food"]
        assert "Food: completed" in food.answer.answer
        all_topics = await alice.call("Plan a team lunch: food, place, and budget.")
        assert len(all_topics.answer.references) == 3
        assert "240 dollars" in all_topics.answer.answer
        bob = PeerClient(settings, "coordinator", events.append, owner="bob")
        partial = await bob.call("Plan a team lunch: food, place, and budget.")
        assert partial.answer.answer.startswith("Partial lunch plan")
        assert {ref.fixture_id for ref in partial.answer.references} == {
            "lunch-food",
            "lunch-place",
        }
        assert "240" not in partial.answer.answer
        with pytest.raises(LookupFailure):
            await PeerClient(settings, "security", events.append, owner="bob").call("budget")
        wrong_scenario = settings.model_copy(update={"demo_scenario": "engineering"})
        with pytest.raises(LookupFailure):
            await PeerClient(wrong_scenario, "runbook", events.append).call("runbook")
