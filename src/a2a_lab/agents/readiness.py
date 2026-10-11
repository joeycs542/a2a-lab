"""A fixture workflow demonstrating an extension of the knowledge-agent role."""

import re
from importlib.resources import files

from a2a_lab.agents.fixtures import apply_fixture_controls
from a2a_lab.domain.models import Answer, Reference


class ReleaseReadinessAgent:
    """Return a bundled checklist; never inspect systems or approve a release."""

    def __init__(self, delay_seconds: float = 2) -> None:
        self._delay_seconds = delay_seconds
        self._note = (
            files("a2a_lab.agents").joinpath("notes", "release-readiness.md").read_text("utf-8")
        )

    async def answer(self, question: str) -> Answer:
        """Answer matching questions with one stable fixture citation."""
        await apply_fixture_controls(question, self._delay_seconds)
        words = frozenset(re.findall(r"[a-z]+", question.lower()))
        if not words & {"release", "readiness", "rollout", "rollback", "deployment"}:
            return Answer(
                answer="Ask about the bundled release readiness checklist.", references=()
            )
        return Answer(
            answer=self._note.strip(),
            references=(
                Reference(fixture_id="release-readiness", title="Release readiness checklist"),
            ),
        )
