"""Recipient-independent synthetic resource policy shared by catalog and execution."""

from a2a_lab.domain.roles import SpecialistName
from a2a_lab.security.identity import Owner


def permitted_peer(peer: SpecialistName, owner: Owner) -> bool:
    """Teaching policy: Bob may use operations/release; security is Alice-only."""
    return peer != "security" or owner == "alice"
