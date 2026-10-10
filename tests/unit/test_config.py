from pathlib import Path

import pytest
from pydantic import ValidationError

from a2a_lab.cli import main
from a2a_lab.config import Settings


@pytest.mark.parametrize(
    "values",
    [
        {"host": "0.0.0.0"},
        {"host": "192.168.1.2"},
        {"profile": "production"},
        {"port": 0},
        {"port": 65536},
        {"port": "not-a-port"},
        {"request_timeout_seconds": 0},
        {"request_timeout_seconds": float("inf")},
        {"request_timeout_seconds": float("nan")},
        {"max_input_characters": 0},
    ],
)
def test_unsafe_or_invalid_configuration_is_rejected(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **values)


def test_environment_and_ipv6_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("A2A_LAB_HOST", "::1")
    monkeypatch.setenv("A2A_LAB_PORT", "8200")
    settings = Settings(_env_file=None)
    assert settings.rpc_url == "http://[::1]:8200/a2a/jsonrpc"
    assert settings.profile == "local-demo"


def test_dotenv_configuration(tmp_path: Path) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("A2A_LAB_PORT=8200\nA2A_LAB_MAX_INPUT_CHARACTERS=40\n")
    settings = Settings(_env_file=dotenv)
    assert settings.port == 8200
    assert settings.max_input_characters == 40


def test_cli_rejects_configuration_without_disclosing_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("PRIVATE_KEY=do-not-print-this\n")
    assert main(["doctor"]) == 2
    output = capsys.readouterr()
    assert "Invalid lab configuration" in output.err
    assert "do-not-print-this" not in output.err + output.out
