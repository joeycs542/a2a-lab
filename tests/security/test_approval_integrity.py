import asyncio

import pytest

from a2a_lab.domain.models import Answer
from a2a_lab.security.approval import ApprovalRequest, ApprovalStore, ExecutionRequest, ReleaseTerms
from a2a_lab.security.identity import Principal, SecurityError

ALICE = Principal(actor="alice", owner="alice", role="user", audience="coordinator")
BOB = Principal(actor="bob", owner="bob", role="user", audience="coordinator")
HUMAN = Principal(actor="human-alice", owner="alice", role="approver", audience="coordinator")
FIXTURE = Answer(answer="Synthetic fixture to display", references=())
TERMS = ReleaseTerms(task_id="task", artifact_id="artifact")


async def setup(clock=lambda: 100.0):
    store = ApprovalStore(20, clock)
    proposal = await store.propose(ALICE, TERMS, FIXTURE)
    grant = await store.approve(
        HUMAN,
        ApprovalRequest(
            proposal_id=proposal.proposal_id,
            expected_digest=proposal.digest,
            terms=proposal.terms,
            ttl_seconds=1,
        ),
    )
    request = ExecutionRequest(
        proposal_id=proposal.proposal_id,
        approval_id=grant.approval_id,
        terms=proposal.terms,
        idempotency_key="one-release",
    )
    return store, proposal, grant, request


@pytest.mark.parametrize(
    "alteration", ["missing", "actor", "terms", "revision", "content", "expired"]
)
async def test_execution_requires_exact_valid_approval(alteration: str) -> None:
    now = [100.0]
    store, _, _, request = await setup(lambda: now[0])
    principal, content = ALICE, FIXTURE
    if alteration == "missing":
        request = request.model_copy(update={"approval_id": "not-issued"})
    elif alteration == "actor":
        principal = BOB
    elif alteration == "terms":
        request = request.model_copy(
            update={"terms": TERMS.model_copy(update={"label": "Changed"})}
        )
    elif alteration == "revision":
        request = request.model_copy(update={"terms": TERMS.model_copy(update={"revision": 2})})
    elif alteration == "content":
        content = Answer(answer="different artifact", references=())
    else:
        now[0] = 102.0
    with pytest.raises(SecurityError):
        await store.execute(principal, request, content)


async def test_agent_or_wrong_human_cannot_create_approval() -> None:
    store = ApprovalStore(20)
    proposal = await store.propose(ALICE, TERMS, FIXTURE)
    request = ApprovalRequest(
        proposal_id=proposal.proposal_id, expected_digest=proposal.digest, terms=proposal.terms
    )
    with pytest.raises(SecurityError):
        await store.approve(ALICE, request)
    wrong = Principal(actor="human-bob", owner="bob", role="approver", audience="coordinator")
    with pytest.raises(SecurityError):
        await store.approve(wrong, request)
    with pytest.raises(SecurityError):
        await store.approve(
            HUMAN,
            request.model_copy(update={"terms": TERMS.model_copy(update={"label": "Changed"})}),
        )


async def test_concurrent_retries_return_one_receipt_and_changed_retry_is_denied() -> None:
    now = [100.0]
    store, _, _, request = await setup(lambda: now[0])
    receipts = await asyncio.gather(*(store.execute(ALICE, request, FIXTURE) for _ in range(20)))
    assert len({receipt.release_id for receipt in receipts}) == 1
    now[0] = 102.0
    assert (await store.execute(ALICE, request, FIXTURE)).release_id == receipts[0].release_id
    with pytest.raises(SecurityError):
        await store.execute(
            ALICE,
            request.model_copy(update={"terms": TERMS.model_copy(update={"label": "Changed"})}),
            FIXTURE,
        )


async def test_concurrent_new_keys_cannot_replay_authority() -> None:
    store, _, _, request = await setup()
    results = await asyncio.gather(
        *(
            store.execute(
                ALICE, request.model_copy(update={"idempotency_key": f"attempt-{index}"}), FIXTURE
            )
            for index in range(20)
        ),
        return_exceptions=True,
    )
    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, SecurityError) for result in results) == 19


async def test_second_grant_cannot_release_same_proposal_twice() -> None:
    store, proposal, _, request = await setup()
    second = await store.approve(
        HUMAN,
        ApprovalRequest(
            proposal_id=proposal.proposal_id, expected_digest=proposal.digest, terms=proposal.terms
        ),
    )
    await store.execute(ALICE, request, FIXTURE)
    with pytest.raises(SecurityError):
        await store.execute(
            ALICE,
            request.model_copy(
                update={"approval_id": second.approval_id, "idempotency_key": "second-release"}
            ),
            FIXTURE,
        )


async def test_approval_and_proposal_storage_is_bounded() -> None:
    store = ApprovalStore(1)
    proposal = await store.propose(ALICE, TERMS, FIXTURE)
    with pytest.raises(SecurityError, match="capacity"):
        await store.propose(ALICE, TERMS, FIXTURE)
    request = ApprovalRequest(
        proposal_id=proposal.proposal_id, expected_digest=proposal.digest, terms=proposal.terms
    )
    await store.approve(HUMAN, request)
    with pytest.raises(SecurityError, match="capacity"):
        await store.approve(HUMAN, request)
