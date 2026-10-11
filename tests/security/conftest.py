from pathlib import Path

import pytest

from a2a_lab.config import Settings
from a2a_lab.security.identity import initialize_security


@pytest.fixture
def secure_settings(tmp_path: Path) -> Settings:
    directory = tmp_path / "security"
    initialize_security(directory)
    return Settings(
        _env_file=None,
        profile="local-secure",
        credentials_directory=directory,
        fixture_delay_seconds=0.2,
    )
