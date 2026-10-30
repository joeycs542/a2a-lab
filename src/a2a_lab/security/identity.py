"""Recipient-bound local credentials and trusted request identities."""

import hashlib
import json
import os
import secrets
import time
from contextvars import ContextVar
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from a2a_lab.domain.roles import ServiceName, Topology, services_for

AgentAudience = ServiceName
Owner = Literal["alice", "bob"]


class SecurityError(ValueError):
    """Local credential or authority validation failed."""


class ExpiredCredentialError(SecurityError):
    """A local teaching credential expired before it could be sent."""


class Principal(BaseModel):
    """Identity fields derived exclusively from a configured verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    actor: Literal["alice", "bob", "coordinator", "human-alice", "human-bob"]
    owner: Owner
    role: Literal["user", "service", "approver"]
    audience: AgentAudience

    @property
    def scope(self) -> str:
        """Keep direct user and represented service tasks isolated."""
        return f"{self.actor}:{self.owner}"


current_principal: ContextVar[Principal | None] = ContextVar("lab_principal", default=None)
current_correlation: ContextVar[str] = ContextVar("lab_correlation", default="local-demo")


class Verifier(BaseModel):
    """Server-side token digest, immutable identity, and expiry."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    principal: Principal
    expires_at: float = Field(allow_inf_nan=False)


class Credential(BaseModel):
    """A secret bound to a single recipient and acting identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    token: SecretStr
    principal: Principal
    expires_at: float = Field(allow_inf_nan=False)

    def bearer(self) -> str:
        """Refuse to send an expired locally issued credential."""
        if self.expires_at <= time.time():
            raise ExpiredCredentialError(
                "Local credentials expired; generate a new security directory."
            )
        return f"Bearer {self.token.get_secret_value()}"


class ServerKeys(BaseModel):
    """Each server receives verifiers and only its outbound service tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    verifiers: tuple[Verifier, ...]
    outbound: tuple[Credential, ...] = ()

    def authenticate(self, authorization: str, audience: AgentAudience) -> Principal:
        """Match a random bearer token by digest, recipient, and expiry."""
        if not authorization.startswith("Bearer ") or len(authorization) > 256:
            raise SecurityError("Authentication failed.")
        token = authorization[7:]
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        for record in self.verifiers:
            if (
                secrets.compare_digest(digest, record.digest)
                and record.principal.audience == audience
                and record.expires_at > time.time()
            ):
                return record.principal
        raise SecurityError("Authentication failed.")

    def delegated(self, owner: Owner, audience: AgentAudience = "knowledge") -> Credential:
        """Choose configured authority; request text cannot change the owner."""
        for credential in self.outbound:
            if (
                credential.principal.owner == owner
                and credential.principal.actor == "coordinator"
                and credential.principal.role == "service"
                and credential.principal.audience == audience
            ):
                return credential
        raise SecurityError("No authorized delegation credential.")


class ClientKeys(BaseModel):
    """Operator-held user and separate human-control credentials."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    credentials: tuple[Credential, ...]

    def select(
        self, owner: Owner, audience: AgentAudience, *, approval: bool = False
    ) -> Credential:
        """Choose one fixed credential without exposing it to agent text."""
        role = "approver" if approval else "user"
        for credential in self.credentials:
            if (
                credential.principal.owner == owner
                and credential.principal.audience == audience
                and credential.principal.role == role
            ):
                return credential
        raise SecurityError("No matching operator credential.")


def _read_private(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise SecurityError("Credential file is missing or is a symbolic link.")
    info = path.stat()
    if os.name == "posix" and (info.st_mode & 0o077 or info.st_uid != os.getuid()):
        raise SecurityError("Credential files must be owned by the current user with mode 0600.")
    if info.st_size > 65536:
        raise SecurityError("Credential file exceeds its size limit.")
    return path.read_text(encoding="utf-8")


def load_server_keys(directory: Path, audience: AgentAudience) -> ServerKeys:
    """Load only this server's configured authority."""
    try:
        return ServerKeys.model_validate_json(_read_private(directory / f"{audience}.json"))
    except (OSError, ValueError) as error:
        raise SecurityError("Local server credentials are missing or invalid.") from error


def load_client_keys(directory: Path) -> ClientKeys:
    """Load the operator's private local credential file."""
    try:
        return ClientKeys.model_validate_json(_read_private(directory / "clients.json"))
    except (OSError, ValueError) as error:
        raise SecurityError("Local operator credentials are missing or invalid.") from error


def initialize_security(
    directory: Path, ttl_seconds: int = 3600, *, topology: Topology = "baseline"
) -> None:
    """Create a fresh private directory; never overwrite existing credentials."""
    if not 1 <= ttl_seconds <= 86400:
        raise SecurityError("Credential lifetime must be between 1 and 86400 seconds.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    audiences = services_for(topology)
    records: dict[AgentAudience, list[dict[str, object]]] = {a: [] for a in audiences}
    clients: list[dict[str, object]] = []
    delegated: list[dict[str, object]] = []
    expires = time.time() + ttl_seconds

    def issue(principal: Principal, destination: list[dict[str, object]]) -> None:
        token = secrets.token_urlsafe(32)
        destination.append(
            {"token": token, "principal": principal.model_dump(), "expires_at": expires}
        )
        records[principal.audience].append(
            {
                "digest": hashlib.sha256(token.encode()).hexdigest(),
                "principal": principal.model_dump(),
                "expires_at": expires,
            }
        )

    humans: dict[Owner, Literal["human-alice", "human-bob"]] = {
        "alice": "human-alice",
        "bob": "human-bob",
    }
    for owner in ("alice", "bob"):
        for audience in audiences:
            issue(Principal(actor=owner, owner=owner, role="user", audience=audience), clients)
        issue(
            Principal(actor=humans[owner], owner=owner, role="approver", audience="coordinator"),
            clients,
        )
        for audience in audiences:
            if audience != "coordinator":
                issue(
                    Principal(actor="coordinator", owner=owner, role="service", audience=audience),
                    delegated,
                )
    documents: dict[str, object] = {"clients.json": {"credentials": clients}}
    for audience in audiences:
        documents[f"{audience}.json"] = {
            "verifiers": records[audience],
            "outbound": delegated if audience == "coordinator" else [],
        }
    for name, content in documents.items():
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(content, stream, indent=2)
