"""Exact-term human approval and atomic synthetic release receipts."""

import asyncio
import hashlib
import json
import time
from collections.abc import Callable
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from a2a_lab.domain.models import Answer
from a2a_lab.security.identity import Principal, SecurityError


class ReleaseTerms(BaseModel):
    """The only supported synthetic commitment; no arbitrary destination."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    operation: Literal["release-fixture"] = "release-fixture"
    destination: Literal["local-display"] = "local-display"
    task_id: str = Field(min_length=1, max_length=128)
    artifact_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=1, ge=1, le=10000)
    label: str = Field(default="Teaching fixture", min_length=1, max_length=100)


class Proposal(BaseModel):
    """Application-held resource snapshot presented for human review."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str
    owner_scope: str
    terms: ReleaseTerms
    content_digest: str
    digest: str


class ApprovalRequest(BaseModel):
    """A human acknowledges the digest of the exact displayed proposal."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str = Field(min_length=1, max_length=128)
    expected_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    terms: ReleaseTerms
    ttl_seconds: int = Field(default=60, ge=1, le=300)


class Grant(BaseModel):
    """Authority created only after an authenticated human approval."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    approval_id: str
    proposal_id: str
    owner_scope: str
    approved_by: str
    digest: str
    expires_at: float


class ExecutionRequest(BaseModel):
    """An execution must present the exact terms and its retry identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    proposal_id: str = Field(min_length=1, max_length=128)
    approval_id: str = Field(min_length=1, max_length=128)
    idempotency_key: str = Field(min_length=1, max_length=128)
    terms: ReleaseTerms


class Receipt(BaseModel):
    """Confirmed local display result retained for legitimate retries."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    release_id: str
    proposal_id: str
    approval_id: str
    terms: ReleaseTerms
    fixture: Answer


def content_digest(content: Answer) -> str:
    """Fingerprint validated content rather than trusting an agent revision."""
    data = json.dumps(content.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class ApprovalStore:
    """Serialize authorization consumption and the one local commitment."""

    def __init__(self, maximum: int, clock: Callable[[], float] = time.time) -> None:
        self._maximum = maximum
        self._clock = clock
        self._proposals: dict[str, Proposal] = {}
        self._grants: dict[str, Grant] = {}
        self._receipts: dict[tuple[str, str], Receipt] = {}
        self._consumed: set[str] = set()
        self._released: set[str] = set()
        self._lock = asyncio.Lock()

    async def propose(self, principal: Principal, terms: ReleaseTerms, content: Answer) -> Proposal:
        """Store exact terms and a completed artifact snapshot for review."""
        if principal.role != "user":
            raise SecurityError("Proposal not permitted.")
        snapshot = content_digest(content)
        digest = hashlib.sha256(
            json.dumps(
                {"scope": principal.scope, "terms": terms.model_dump(), "content": snapshot},
                sort_keys=True,
            ).encode()
        ).hexdigest()
        async with self._lock:
            if len(self._proposals) >= self._maximum:
                raise SecurityError("Proposal capacity reached.")
            proposal = Proposal(
                proposal_id=str(uuid4()),
                owner_scope=principal.scope,
                terms=terms,
                content_digest=snapshot,
                digest=digest,
            )
            self._proposals[proposal.proposal_id] = proposal
            return proposal

    async def approve(self, principal: Principal, request: ApprovalRequest) -> Grant:
        """Authorize only the human's user scope and reviewed exact digest."""
        async with self._lock:
            proposal = self._proposals.get(request.proposal_id)
            if (
                principal.role != "approver"
                or proposal is None
                or proposal.owner_scope != f"{principal.owner}:{principal.owner}"
                or proposal.digest != request.expected_digest
                or proposal.terms != request.terms
                or proposal.proposal_id in self._released
            ):
                raise SecurityError("Approval not permitted.")
            if len(self._grants) >= self._maximum:
                raise SecurityError("Approval capacity reached.")
            grant = Grant(
                approval_id=str(uuid4()),
                proposal_id=proposal.proposal_id,
                owner_scope=proposal.owner_scope,
                approved_by=principal.actor,
                digest=proposal.digest,
                expires_at=self._clock() + request.ttl_seconds,
            )
            self._grants[grant.approval_id] = grant
            return grant

    async def execute(
        self, principal: Principal, request: ExecutionRequest, content: Answer
    ) -> Receipt:
        """Commit once atomically; the same exact retry returns its receipt."""
        if principal.role != "user":
            raise SecurityError("Execution not permitted.")
        async with self._lock:
            key = (principal.scope, request.idempotency_key)
            cached = self._receipts.get(key)
            if cached is not None:
                if (
                    cached.proposal_id != request.proposal_id
                    or cached.approval_id != request.approval_id
                    or cached.terms != request.terms
                    or content_digest(cached.fixture) != content_digest(content)
                ):
                    raise SecurityError("Retry terms differ from the committed action.")
                return cached
            proposal = self._proposals.get(request.proposal_id)
            grant = self._grants.get(request.approval_id)
            if (
                proposal is None
                or grant is None
                or proposal.owner_scope != principal.scope
                or grant.owner_scope != principal.scope
                or grant.proposal_id != proposal.proposal_id
                or grant.digest != proposal.digest
                or request.terms != proposal.terms
                or content_digest(content) != proposal.content_digest
                or grant.expires_at <= self._clock()
                or grant.approval_id in self._consumed
                or proposal.proposal_id in self._released
            ):
                raise SecurityError("Exact valid human approval is required.")
            if len(self._receipts) >= self._maximum:
                raise SecurityError("Release capacity reached.")
            receipt = Receipt(
                release_id=str(uuid4()),
                proposal_id=proposal.proposal_id,
                approval_id=grant.approval_id,
                terms=proposal.terms,
                fixture=content,
            )
            self._consumed.add(grant.approval_id)
            self._released.add(proposal.proposal_id)
            self._receipts[key] = receipt
            return receipt
