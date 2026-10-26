import json
import os
from pathlib import Path

import pytest

from a2a_lab.container_credentials import prepare_credentials
from a2a_lab.security.identity import SecurityError, load_client_keys, load_server_keys


def test_container_volumes_separate_authority_and_reuse_existing_keys(tmp_path: Path) -> None:
    prepare_credentials(tmp_path)
    original = {path: path.read_bytes() for path in tmp_path.glob("*/*.json")}
    assert len(original) == 3
    assert {path.name for path in (tmp_path / "knowledge").iterdir()} == {"knowledge.json"}
    assert not load_server_keys(tmp_path / "knowledge", "knowledge").outbound
    clients = load_client_keys(tmp_path / "operator")
    assert all(credential.principal.actor != "coordinator" for credential in clients.credentials)
    if os.name == "posix":
        assert all(path.stat().st_mode & 0o077 == 0 for path in original)
        assert all(path.parent.stat().st_mode & 0o077 == 0 for path in original)
    prepare_credentials(tmp_path)
    assert {path: path.read_bytes() for path in original} == original


def test_partial_container_credentials_are_rejected_without_overwrite(tmp_path: Path) -> None:
    prepare_credentials(tmp_path)
    original = (tmp_path / "operator" / "clients.json").read_bytes()
    (tmp_path / "knowledge" / "knowledge.json").unlink()
    with pytest.raises(SecurityError):
        prepare_credentials(tmp_path)
    assert (tmp_path / "operator" / "clients.json").read_bytes() == original
    assert not (tmp_path / "knowledge" / "knowledge.json").exists()


def test_expired_container_credentials_require_explicit_reset(tmp_path: Path) -> None:
    prepare_credentials(tmp_path)
    path = tmp_path / "operator" / "clients.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    for credential in document["credentials"]:
        credential["expires_at"] = 0
    path.write_text(json.dumps(document), encoding="utf-8")
    original = path.read_bytes()
    with pytest.raises(SecurityError, match="expired"):
        prepare_credentials(tmp_path)
    assert path.read_bytes() == original


def test_discovery_issuer_separates_every_recipient_and_reuses_keys(tmp_path: Path) -> None:
    prepare_credentials(tmp_path, "discovery")
    original = {path: path.read_bytes() for path in tmp_path.glob("*/*.json")}
    assert len(original) == 7
    for audience in ("runbook", "security", "release", "directory"):
        assert not load_server_keys(tmp_path / audience, audience).outbound
    coordinator = load_server_keys(tmp_path / "coordinator", "coordinator")
    for owner in ("alice", "bob"):
        for audience in ("runbook", "security", "release", "directory"):
            credential = coordinator.delegated(owner, audience)
            recipient = load_server_keys(tmp_path / audience, audience)
            assert recipient.authenticate(credential.bearer(), audience).owner == owner
            with pytest.raises(SecurityError):
                load_server_keys(tmp_path / "knowledge", "knowledge").authenticate(
                    credential.bearer(), "knowledge"
                )
    prepare_credentials(tmp_path, "discovery")
    assert {path: path.read_bytes() for path in original} == original


def test_baseline_credentials_cannot_be_silently_upgraded(tmp_path: Path) -> None:
    prepare_credentials(tmp_path)
    original = {path: path.read_bytes() for path in tmp_path.glob("*/*.json")}
    with pytest.raises(SecurityError):
        prepare_credentials(tmp_path, "discovery")
    assert {path: path.read_bytes() for path in tmp_path.glob("*/*.json")} == original
