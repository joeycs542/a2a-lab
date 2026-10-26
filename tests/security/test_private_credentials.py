import json
import os
from pathlib import Path

import pytest

from a2a_lab.cli import main
from a2a_lab.security.identity import (
    SecurityError,
    initialize_security,
    load_client_keys,
    load_server_keys,
)


def test_private_generation_preserves_existing_files_and_separates_server_keys(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "credentials"
    initialize_security(directory)
    original = (directory / "clients.json").read_bytes()
    with pytest.raises(FileExistsError):
        initialize_security(directory)
    assert (directory / "clients.json").read_bytes() == original
    if os.name == "posix":
        assert directory.stat().st_mode & 0o077 == 0
        assert all(path.stat().st_mode & 0o077 == 0 for path in directory.iterdir())
    coordinator = load_server_keys(directory, "coordinator")
    knowledge = load_server_keys(directory, "knowledge")
    assert not knowledge.outbound
    assert all(
        key.principal.role == "service" and key.principal.audience == "knowledge"
        for key in coordinator.outbound
    )
    assert all(key.principal.actor == "coordinator" for key in coordinator.outbound)


def test_credential_values_are_not_printed_or_serialized_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    directory = tmp_path / "credentials"
    assert main(["init-security", "--directory", str(directory)]) == 0
    keys = load_client_keys(directory)
    output = capsys.readouterr()
    assert all(
        key.token.get_secret_value() not in output.out + output.err for key in keys.credentials
    )
    assert all(
        key.token.get_secret_value() not in repr(keys) + keys.model_dump_json()
        for key in keys.credentials
    )


def test_corrupt_or_insecure_credentials_fail_without_disclosing_contents(tmp_path: Path) -> None:
    directory = tmp_path / "credentials"
    initialize_security(directory)
    path = directory / "clients.json"
    path.write_text('{"token": "private-do-not-display", broken}', encoding="utf-8")
    with pytest.raises(SecurityError) as error:
        load_client_keys(directory)
    assert "private-do-not-display" not in str(error.value)
    path.write_text(json.dumps({"credentials": []}), encoding="utf-8")
    if os.name == "posix":
        path.chmod(0o644)
        with pytest.raises(SecurityError):
            load_client_keys(directory)


def test_secure_profile_cannot_run_the_unauthenticated_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("A2A_LAB_PROFILE", "local-secure")
    assert main(["serve-probe"]) == 2
    assert main(["check-sdk"]) == 2
