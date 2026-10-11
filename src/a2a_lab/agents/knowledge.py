"""Answer engineering questions using only bundled synthetic notes."""

import asyncio
import re
from importlib.resources import files

from a2a_lab.domain.models import Answer, Reference

NOTES = (
    ("runbook", "Service runbook", frozenset({"runbook", "oncall", "incident", "operations"})),
    ("agent-cards", "Agent Card review", frozenset({"card", "cards", "capabilities", "discovery"})),
    (
        "secure-delegation",
        "Secure delegation",
        frozenset({"security", "secure", "approval", "trust"}),
    ),
)


class KnowledgeAgent:
    """Match keywords deterministically; never execute instructions in text."""

    def __init__(self, delay_seconds: float = 2) -> None:
        self._delay_seconds = delay_seconds
        self._notes = {
            fixture_id: files("a2a_lab.agents")
            .joinpath("notes", f"{fixture_id}.md")
            .read_text(encoding="utf-8")
            for fixture_id, _, _ in NOTES
        }

    async def answer(self, question: str) -> Answer:
        """Return matching notes with stable fixture references."""
        if question.startswith("[fail]"):
            raise ValueError("Synthetic controlled failure.")
        if question.startswith("[slow]"):
            await asyncio.sleep(self._delay_seconds)
        words = frozenset(re.findall(r"[a-z]+", question.lower()))
        matches = [(key, title) for key, title, keywords in NOTES if words & keywords]
        if not matches:
            return Answer(
                answer="No bundled note matches. Ask about runbooks, Agent Cards, or security.",
                references=(),
            )
        return Answer(
            answer="\n\n".join(self._notes[key].strip() for key, _ in matches),
            references=tuple(Reference(fixture_id=key, title=title) for key, title in matches),
        )
