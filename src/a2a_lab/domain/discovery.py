"""Bounded catalog contracts and deterministic topic matching."""

import re

from pydantic import BaseModel, ConfigDict, Field

from a2a_lab.domain.roles import SpecialistName
from a2a_lab.domain.scenarios import TOPICS, DemoScenario


def topic_scores(
    question: str, scenario: DemoScenario = "engineering"
) -> dict[SpecialistName, int]:
    """Match configured topics; a general lunch request asks all lunch agents."""
    words = frozenset(re.findall(r"[a-z]+", question.lower()))
    scores = {peer: len(words & topic.words) for peer, topic in TOPICS[scenario].items()}
    if scenario == "team-lunch" and "lunch" in words and not any(scores.values()):
        return dict.fromkeys(scores, 1)
    return scores


class SearchRequest(BaseModel):
    """Search topics only; caller identity never comes from the request body."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    topics: tuple[SpecialistName, ...] = Field(min_length=1, max_length=3)


class Candidate(BaseModel):
    """Untrusted directory data to compare against independent deployment policy."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    peer_id: SpecialistName
    skill_id: str = Field(min_length=1, max_length=100)
    card_url: str = Field(min_length=1, max_length=200)
    rpc_url: str = Field(min_length=1, max_length=200)


class SearchResult(BaseModel):
    """A finite result set with no permission to add endpoints or credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    candidates: tuple[Candidate, ...] = Field(max_length=3)
