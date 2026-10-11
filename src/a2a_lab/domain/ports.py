"""The coordinator's narrow dependency on a knowledge provider."""

from typing import Protocol

from a2a_lab.domain.models import Answer


class KnowledgeLookup(Protocol):
    """Return validated knowledge data without exposing SDK wire types."""

    async def answer(self, question: str) -> Answer:
        """Answer the question or raise a controlled lookup failure."""
        ...
