"""Fixed teaching roles; card content cannot create new network identities."""

from typing import Literal

AgentName = Literal["coordinator", "knowledge", "runbook", "security", "release"]
SpecialistName = Literal["runbook", "security", "release"]
ServiceName = Literal["coordinator", "knowledge", "runbook", "security", "release", "directory"]
Topology = Literal["baseline", "discovery"]
AGENTS: tuple[AgentName, ...] = ("coordinator", "knowledge", "runbook", "security", "release")
SPECIALISTS: tuple[SpecialistName, ...] = ("runbook", "security", "release")


def services_for(topology: Topology) -> tuple[ServiceName, ...]:
    """Keep the original issuer/supervisor topology available."""
    if topology == "discovery":
        return ("knowledge", "directory", "runbook", "security", "release", "coordinator")
    return ("knowledge", "coordinator")
