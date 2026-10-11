from pathlib import Path

import pytest

from a2a_lab.a2a.client import LookupFailure
from a2a_lab.a2a.directory import DiscoveryLookup
from a2a_lab.config import Settings
from a2a_lab.domain.models import Answer, Reference
from a2a_lab.security.identity import initialize_security, load_server_keys


@pytest.mark.parametrize("bad_result", ["size", "citations", "failed"])
async def test_review_rejects_bad_findings_without_losing_other_peer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_result: str
) -> None:
    initialize_security(tmp_path / "keys", topology="discovery")
    settings = Settings(
        _env_file=None,
        profile="local-secure",
        topology="discovery",
        discovery_mode="review",
        credentials_directory=tmp_path / "keys",
    )
    sends: list[str] = []
    reference = Reference(fixture_id="release-readiness", title="Release checklist")

    class FixturePeer:
        def __init__(self, settings: Settings, peer: str, trace: object, **kwargs: object) -> None:
            self.peer = peer

        async def answer(self, question: str) -> Answer:
            sends.append(self.peer)
            if self.peer == "runbook":
                if bad_result == "failed":
                    raise LookupFailure("Known failure", "failed")
                if bad_result == "size":
                    return Answer(answer="x" * 2001, references=())
                return Answer(answer="Finding", references=(reference, reference))
            return Answer(answer="Valid release finding", references=(reference,))

    monkeypatch.setattr("a2a_lab.a2a.directory.PeerClient", FixturePeer)
    lookup = DiscoveryLookup(settings, load_server_keys(tmp_path / "keys", "coordinator"), print)
    result = await lookup.review("runbook release", ["runbook", "release"], False)
    assert "Incomplete review" in result.answer
    assert f"runbook: {'failed' if bad_result == 'failed' else 'invalid'}" in result.answer
    assert "release: completed\nValid release finding" in result.answer
    assert result.references == (reference,)
    assert sorted(sends) == ["release", "runbook"]
