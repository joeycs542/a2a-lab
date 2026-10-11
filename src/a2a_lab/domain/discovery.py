"""Bounded catalog contracts and deterministic topic matching."""

import re

from pydantic import BaseModel, ConfigDict, Field

from a2a_lab.domain.roles import SpecialistName

TOPIC_WORDS: dict[SpecialistName, frozenset[str]] = {
    "runbook": frozenset({"runbook", "oncall", "incident", "operations"}),
    "security": frozenset({"security", "secure", "approval", "trust"}),
    "release": frozenset({"release", "readiness", "rollout", "rollback", "deployment"}),
}


def topic_scores(question: str) -> dict[SpecialistName, int]:
    """Count distinct supported keywords, with no generated routing authority."""
    words = frozenset(re.findall(r"[a-z]+", question.lower()))
    return {topic: len(words & keywords) for topic, keywords in TOPIC_WORDS.items()}


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
