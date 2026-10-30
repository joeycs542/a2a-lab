"""Load trusted, packaged model instructions selected by startup configuration."""

from importlib.resources import files
from typing import Literal

ModelRole = Literal["knowledge", "runbook", "security", "release", "food", "budget", "place"]
PromptProfile = Literal["generic", "role", "guided"]


def system_prompt(role: ModelRole, profile: PromptProfile) -> str:
    """Compose a fixed role and optional task guide; never resolve request paths."""
    if role not in {"knowledge", "runbook", "security", "release", "food", "budget", "place"}:
        raise ValueError("Unsupported model role.")
    if profile not in {"generic", "role", "guided"}:
        raise ValueError("Unsupported prompt profile.")
    root = files("a2a_lab.agents").joinpath("runtime_prompts")
    parts = [root.joinpath("base.md").read_text(encoding="utf-8")]
    if profile != "generic":
        parts.append(root.joinpath("roles", f"{role}.md").read_text(encoding="utf-8"))
    if profile == "guided":
        parts.append(root.joinpath("skills", f"{role}.md").read_text(encoding="utf-8"))
    return "\n\n".join(part.strip() for part in parts)
