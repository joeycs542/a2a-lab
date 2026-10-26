"""Delegate one engineering question and compose the validated answer."""

from a2a_lab.domain.models import Answer
from a2a_lab.domain.ports import KnowledgeLookup


class CoordinatorAgent:
    """Make exactly one lookup; peer data cannot request further delegation."""

    def __init__(self, knowledge: KnowledgeLookup) -> None:
        self._knowledge = knowledge

    async def answer(self, question: str) -> Answer:
        """Compose a result without treating peer output as instructions."""
        result = await self._knowledge.answer(question)
        return Answer(
            answer=f"Knowledge agent findings:\n\n{result.answer}", references=result.references
        )
