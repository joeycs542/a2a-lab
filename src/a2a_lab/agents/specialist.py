"""Independent specialist fixtures sharing the existing domain result contract."""

from importlib.resources import files

from a2a_lab.agents.fixtures import apply_fixture_controls
from a2a_lab.domain.discovery import topic_scores
from a2a_lab.domain.models import Answer, Reference
from a2a_lab.domain.roles import SpecialistName
from a2a_lab.domain.scenarios import TOPICS, DemoScenario


class SpecialistAgent:
    """Answer one supported topic; never inspect systems or authorize actions."""

    def __init__(
        self,
        topic: SpecialistName,
        delay_seconds: float = 2,
        scenario: DemoScenario = "engineering",
    ) -> None:
        self._topic = topic
        self._delay_seconds = delay_seconds
        self._scenario = scenario
        details = TOPICS[scenario][topic]
        self._fixture_id, self._title = details.fixture, details.source
        self._note = (
            files("a2a_lab.agents")
            .joinpath("notes", f"{self._fixture_id}.md")
            .read_text(encoding="utf-8")
        )

    async def answer(self, question: str) -> Answer:
        """Apply the same cooperative delay/failure controls as baseline fixtures."""
        await apply_fixture_controls(question, self._delay_seconds)
        if not topic_scores(question, self._scenario)[self._topic]:
            return Answer(
                answer=f"Ask about {TOPICS[self._scenario][self._topic].name.lower()}.",
                references=(),
            )
        return Answer(
            answer=self._note.strip(),
            references=(Reference(fixture_id=self._fixture_id, title=self._title),),
        )
