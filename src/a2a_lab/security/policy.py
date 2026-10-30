"""Recipient-independent synthetic resource policy shared by catalog and execution."""

from a2a_lab.domain.roles import SpecialistName
from a2a_lab.security.identity import Owner


def permitted_peer(peer: SpecialistName, owner: Owner) -> bool:
    """Restrict one configured role to Alice: Security or the lunch Budget agent."""
    return peer != "security" or owner == "alice"
