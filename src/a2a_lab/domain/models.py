"""Validated application results shared by the teaching workflows."""

from pydantic import BaseModel, ConfigDict, Field


class Reference(BaseModel):
    """A citation to a bundled synthetic note, never an external URL."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    fixture_id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    title: str = Field(min_length=1, max_length=200)


class Answer(BaseModel):
    """Bounded data returned by a workflow or validated at a peer boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    answer: str = Field(min_length=1, max_length=8192)
    references: tuple[Reference, ...] = Field(max_length=4)
