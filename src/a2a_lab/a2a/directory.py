"""Authenticated catalog search with independent peer policy validation."""

import asyncio

import httpx
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from a2a_lab.a2a.cards import required_skill_id
from a2a_lab.a2a.client import LookupFailure, PeerClient, TraceSink
from a2a_lab.a2a.limits import BoundaryError, BoundedTransport, RequestLimits
from a2a_lab.config import RPC_PATH, Settings
from a2a_lab.domain.discovery import Candidate, SearchRequest, SearchResult, topic_scores
from a2a_lab.domain.models import Answer, Reference
from a2a_lab.domain.roles import SpecialistName
from a2a_lab.domain.scenarios import section_name
from a2a_lab.security.http import LocalAuthentication
from a2a_lab.security.identity import (
    Owner,
    SecurityError,
    ServerKeys,
    current_principal,
    load_client_keys,
)
from a2a_lab.security.policy import permitted_peer


def expected_candidate(peer: SpecialistName, settings: Settings) -> Candidate:
    """Trusted endpoint/capability binding independent of directory responses."""
    base = settings.agent_base_url(peer)
    return Candidate(
        peer_id=peer,
        skill_id=required_skill_id(peer, settings),
        card_url=f"{base}/.well-known/agent-card.json",
        rpc_url=f"{base}{RPC_PATH}",
    )


def create_directory_app(settings: Settings, keys: ServerKeys, trace: TraceSink) -> Starlette:
    """Serve a read-only, bounded catalog; no registration or arbitrary URLs."""
    if settings.topology != "discovery" or settings.profile != "local-secure":
        raise SecurityError("The directory requires authenticated discovery settings.")

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def search(request: Request) -> JSONResponse:
        try:
            query = SearchRequest.model_validate(await request.json())
        except ValueError:
            return JSONResponse({"error": "Invalid search request."}, status_code=422)
        principal = current_principal.get()
        if principal is None:
            return JSONResponse({"error": "Authentication required."}, status_code=401)
        candidates = tuple(
            expected_candidate(peer, settings)
            for peer in settings.discovery_peers
            if peer in query.topics and permitted_peer(peer, principal.owner)
        )
        trace(f"directory.results owner={principal.owner} count={len(candidates)}")
        return JSONResponse(SearchResult(candidates=candidates).model_dump(mode="json"))

    return Starlette(
        debug=False,
        routes=[Route("/health", health), Route("/search", search, methods=["POST"])],
        middleware=[
            Middleware(LocalAuthentication, keys=keys, audience="directory", trace=trace),
            Middleware(RequestLimits, settings=settings),
        ],
    )


class DirectoryClient:
    """Authenticate for this recipient and reject substituted search metadata."""

    def __init__(
        self,
        settings: Settings,
        trace: TraceSink,
        *,
        server_keys: ServerKeys | None = None,
        owner: Owner = "alice",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if settings.topology != "discovery" or settings.profile != "local-secure":
            raise SecurityError("Catalog search requires the authenticated discovery topology.")
        self.settings = settings
        self.trace = trace
        self.keys = server_keys
        self.owner = owner
        self.transport = transport

    async def search(self, query: SearchRequest) -> SearchResult:
        """Send a capability query only; never forward the upstream bearer."""
        owner = self.owner
        if self.keys is not None:
            principal = current_principal.get()
            if principal is None or principal.role != "user":
                raise SecurityError("Discovery requires a verified user.")
            owner = principal.owner
            credential = self.keys.delegated(owner, "directory")
        else:
            credential = load_client_keys(self.settings.credentials_directory).select(
                owner, "directory"
            )
        url = f"{self.settings.agent_base_url('directory')}/search"
        self.trace("directory.search")
        try:
            async with (
                asyncio.timeout(self.settings.request_timeout_seconds),
                httpx.AsyncClient(
                    transport=BoundedTransport(
                        frozenset({url}), self.settings.max_payload_bytes, self.transport
                    ),
                    trust_env=False,
                    follow_redirects=False,
                    timeout=self.settings.request_timeout_seconds,
                    headers={
                        "Authorization": credential.bearer(),
                        "Accept-Encoding": "identity",
                    },
                ) as client,
            ):
                response = await client.post(url, json=query.model_dump(mode="json"))
                response.raise_for_status()
                result = SearchResult.model_validate(response.json())
                seen: set[SpecialistName] = set()
                for candidate in result.candidates:
                    peer = candidate.peer_id
                    if (
                        peer in seen
                        or peer not in query.topics
                        or peer not in self.settings.discovery_peers
                        or not permitted_peer(peer, owner)
                        or candidate != expected_candidate(peer, self.settings)
                    ):
                        raise BoundaryError("Catalog candidate violates independent policy.")
                    seen.add(peer)
                return result
        except (httpx.HTTPError, ValueError, TimeoutError) as error:
            self.trace(f"directory.failed category={type(error).__name__}")
            raise LookupFailure("Directory unavailable or outside approved policy.") from error


class DiscoveryLookup:
    """Select authorized, compatible live peers; never recurse or retry sends."""

    def __init__(self, settings: Settings, keys: ServerKeys, trace: TraceSink) -> None:
        self.settings = settings
        self.keys = keys
        self.trace = trace
        self.directory = DirectoryClient(settings, trace, server_keys=keys)

    async def answer(self, question: str) -> Answer:
        """One deadline covers catalog, up to three cards and bounded delegation."""
        scores = topic_scores(question, self.settings.demo_scenario)
        topics = tuple(topic for topic, score in scores.items() if score)
        if not topics:
            self.trace("selection.none reason=no-topic")
            return Answer(
                answer=(
                    "No supported topic matched. Ask about food, a place or the budget."
                    if self.settings.demo_scenario == "team-lunch"
                    else "No supported topic matched. Ask about runbooks, security or releases."
                ),
                references=(),
            )
        async with asyncio.timeout(self.settings.request_timeout_seconds):
            result = await self.directory.search(SearchRequest(topics=topics))
            viable: list[SpecialistName] = []
            for candidate in result.candidates:
                peer = PeerClient(
                    self.settings, candidate.peer_id, self.trace, server_keys=self.keys
                )
                try:
                    await peer.discover()
                except LookupFailure:
                    self.trace(
                        f"selection.excluded agent={candidate.peer_id} reason=card-unavailable"
                    )
                    continue
                viable.append(candidate.peer_id)
            if not viable:
                self.trace("selection.none reason=no-viable-peer")
                return Answer(
                    answer="No authorized, compatible specialist is available for these topics.",
                    references=(),
                )
            if self.settings.discovery_mode == "review":
                return await self.review(question, viable, len(viable) < len(topics))
            highest = max(scores[peer] for peer in viable)
            selected = [peer for peer in viable if scores[peer] == highest]
            if len(selected) != 1:
                self.trace("selection.ambiguous")
                return Answer(
                    answer="Several topics match equally. Ask one topic first: "
                    + ", ".join(
                        section_name(peer, self.settings.demo_scenario) for peer in sorted(selected)
                    )
                    + ".",
                    references=(),
                )
            peer_id = selected[0]
            self.trace(f"selection.selected agent={peer_id} reason=keyword-match")
            answer = await PeerClient(
                self.settings, peer_id, self.trace, server_keys=self.keys
            ).answer(question)
            return Answer(
                answer=(
                    f"Selected specialist: {section_name(peer_id, self.settings.demo_scenario)}\n\n"
                    f"{answer.answer}"
                ),
                references=answer.references,
            )

    async def review(self, question: str, peers: list[SpecialistName], incomplete: bool) -> Answer:
        """At most three owned parallel sends; keep each outcome and reject oversized findings."""

        async def consult(peer: SpecialistName) -> tuple[SpecialistName, str, Answer | None]:
            self.trace(f"selection.selected agent={peer} reason=topic-match")
            try:
                async with asyncio.timeout(self.settings.request_timeout_seconds / 2):
                    result = await PeerClient(
                        self.settings, peer, self.trace, server_keys=self.keys
                    ).answer(question)
                if len(result.answer) > 2000 or len(result.references) > 1:
                    self.trace(f"review.outcome agent={peer} state=invalid")
                    return peer, "invalid", None
                self.trace(f"review.outcome agent={peer} state=completed")
                return peer, "completed", result
            except LookupFailure as error:
                self.trace(f"review.outcome agent={peer} state={error.outcome}")
                return peer, error.outcome, None
            except TimeoutError:
                self.trace(f"review.outcome agent={peer} state=unknown")
                return peer, "unknown", None

        results = await asyncio.gather(*(consult(peer) for peer in peers))
        sections: list[str] = []
        references: list[Reference] = []
        for peer, state, result in results:
            label = section_name(peer, self.settings.demo_scenario)
            if result is None:
                incomplete = True
                sections.append(
                    f"{label}: {state}. No validated findings; no blind retry was sent."
                )
            else:
                sections.append(f"{label}: completed\n{result.answer}")
                references.extend(result.references)
        prefix = (
            "Incomplete review: some requested topics lacked authorized, compatible findings.\n\n"
            if incomplete
            else "Engineering review from the selected specialists:\n\n"
        )
        if self.settings.demo_scenario == "team-lunch":
            if incomplete:
                prefix = "Partial lunch plan: some requested help was not available.\n\n"
            else:
                prefix = "Team lunch plan:\n\n"
        return Answer(answer=prefix + "\n\n".join(sections), references=tuple(references))
