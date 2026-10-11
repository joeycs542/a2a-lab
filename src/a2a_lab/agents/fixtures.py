"""Shared cooperative delay and failure controls for teaching fixtures."""

import asyncio


async def apply_fixture_controls(question: str, delay_seconds: float) -> None:
    """Honor explicit teaching prefixes without executing arbitrary text."""
    if question.startswith("[fail]"):
        raise ValueError("Synthetic controlled failure.")
    if question.startswith("[slow]"):
        await asyncio.sleep(delay_seconds)
